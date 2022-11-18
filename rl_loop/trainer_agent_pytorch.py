"""
@file: trainer_agent_pytorch.py
Created on 31.05.22
@project: CrazyAra
@author: queensgambit

Definition of the main training loop done in pytorch.
Partially based on:
https://gitlab.com/jweil/PommerLearn/-/blob/master/pommerlearn/training/train_cnn.py
"""

import random
import logging
from pathlib import Path
import torch
import torch.nn as nn
from time import time
import datetime
from rtpt import RTPT
from tqdm import tqdm
from torch.optim.optimizer import Optimizer
from torch.nn.modules.loss import _Loss
from torch import Tensor

from rl_loop.main_config import main_config
from rl_loop.train_config import TrainConfig, TrainObjects
from rl_loop.dataset_loader import load_pgn_dataset,_get_loader
from torch_geometric.data import Batch,DataLoader


class TrainerAgentPytorch:
    """Main training loop"""

    def __init__(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        train_config: TrainConfig,
        train_objects: TrainObjects,
        use_rtpt: bool,
    ):
        """
        Class for training the neural network.
        :param net: The NN with loaded parameters that shall be trained.
        :param val_data: The validation data loaded with gluon DataLoader.
        :param train_config: An instance of the TrainConfig data class.
        :param train_objects: Am instance pf the TrainObject data class.
        :param use_rtpt: If True, an RTPT object will be created and modified within this class.
        """
        self.tc = train_config
        self.to = train_objects
        if self.to.metrics is None:
            self.to.metrics = {}
        self._model = model
        self._val_loader = val_loader
        self.x_train = self.yv_train = self.yp_train = None
        self._ctx = get_context(train_config.context, train_config.device_id)

        # define a summary writer that logs data and flushes to the file every 5 seconds
        if self.tc.log_metrics_to_tensorboard:
            from torch.utils.tensorboard import SummaryWriter
            self.sum_writer = SummaryWriter(log_dir=self.tc.export_dir+"logs", flush_secs=5)

        self.policy_loss = SoftCrossEntropyLoss()
        self.value_loss = nn.MSELoss()
        self.wdl_loss = nn.CrossEntropyLoss()
        self.ply_loss = nn.MSELoss()

        # Define the optimizer
        self.optimizer = create_optimizer(self._model, self.tc)

        self.ordering = list(range(self.tc.nb_parts))  # define a list which describes the order of the processed batches

        # few variables which are internally used
        self.val_loss_best = self.val_p_acc_best = self.k_steps_best = \
            self.old_label = self.value_out = self.t_s = None
        self.patience_cnt = self.batch_proc_tmp = None
        # calculate how many log states will be processed
        self.k_steps_end = round(self.tc.total_it / self.tc.batch_steps)
        if self.k_steps_end == 0:
            self.k_steps_end = 1
        self.k_steps = self.cur_it = self.nb_spikes = self.old_val_loss = self.continue_training = self.t_s_steps = None
        self._train_iter = self.graph_exported = self.val_metric_values = self.val_loss = self.val_p_acc = None
        self.val_metric_values_best = None

        self.use_rtpt = use_rtpt

        if use_rtpt:
            # we use k-steps instead of epochs here
            self.rtpt = RTPT(name_initials=self.tc.name_initials, experiment_name='crazyara',
                             max_iterations=self.k_steps_end-self.tc.k_steps_initial)

    def train(self, cur_it=None):
        """
        Training model
        :param cur_it: Current iteration which is used for the learning rate and momentum schedule.
         If set to None it will be initialized
        :return: return_metrics_and_stop_training()
        """

        self._setup_variables(cur_it)
        self._model.train()  # set training mode

        while self.continue_training:
            # reshuffle the ordering of the training game batches (shuffle works in place)
            random.shuffle(self.ordering)

            self.epoch += 1
            logging.info("EPOCH %d", self.epoch)
            logging.info("=========================")
            self.t_s_steps = time()

            for part_id in tqdm(self.ordering):
                train_loader = _get_loader(self.tc,part_id=part_id,dataset_type="train")

                for _, batch in enumerate(train_loader):
                    data = self.train_update(batch)

                    # add the graph representation of the network to the tensorboard log file
                    # if not self.graph_exported and self.tc.log_metrics_to_tensorboard:
                    #     self.sum_writer.add_graph(self._model, data)
                    #     self.graph_exported = True

                    if self.batch_proc_tmp >= self.tc.batch_steps or self.cur_it >= self.tc.total_it:  # show metrics every thousands steps
                        train_metric_values, val_metric_values = self.evaluate(train_loader)

                        if self.use_rtpt:
                            # update process title according to loss
                            self.rtpt.step(subtitle=f"loss={val_metric_values['loss']:2.2f}")
                        if self.tc.use_spike_recovery and (
                                self.old_val_loss * self.tc.spike_thresh < val_metric_values["loss"]
                                or torch.isnan(val_metric_values["loss"])
                        ):  # check for spikes
                            self.nb_spikes += 1
                            logging.warning(
                                "Spike %d/%d occurred - val_loss: %.3f",
                                self.nb_spikes,
                                self.tc.max_spikes,
                                val_metric_values["loss"],
                            )
                            if self.nb_spikes >= self.tc.max_spikes:
                                self.val_loss = val_metric_values["loss"]
                                self.val_p_acc = val_metric_values["policy_acc"]
                                logging.debug("The maximum number of spikes has been reached. Stop training.")
                                # finally stop training because the number of lr drops has been achieved
                                print()
                                print(
                                    "Elapsed time for training(hh:mm:ss): "
                                    + str(datetime.timedelta(seconds=round(time() - self.t_s)))
                                )

                                if self.tc.log_metrics_to_tensorboard:
                                    self.sum_writer.close()
                                return return_metrics_and_stop_training(self.k_steps, val_metric_values, self.k_steps_best,
                                                                        self.val_metric_values_best)

                            logging.debug("Recover to latest checkpoint")
                            model_path = self.tc.export_dir + "weights/model-%.5f-%.3f-%04d.pt" % (
                                self.val_loss_best,
                                self.val_p_acc_best,
                                self.k_steps_best,
                            )  # Load the best model once again
                            logging.debug("load current best model:%s", model_path)
                            load_torch_state(self._model, self.optimizer, model_path, self.tc.device_id)
                            self.k_steps = self.k_steps_best
                            logging.debug("k_step is back at %d", self.k_steps_best)
                            # print the elapsed time
                            self.t_delta = time() - self.t_s_steps
                            print(" - %.ds" % self.t_delta)
                            self.t_s_steps = time()
                        else:
                            # update the val_loss_value to compare with using spike recovery
                            self.old_val_loss = val_metric_values["loss"]
                            # log the metric values to tensorboard
                            self._log_metrics(train_metric_values, global_step=self.k_steps, prefix="train_")
                            self._log_metrics(val_metric_values, global_step=self.k_steps, prefix="val_")

                            # check if a new checkpoint shall be created
                            if self.val_loss_best is None or val_metric_values["loss"] < self.val_loss_best:
                                # update val_loss_best
                                self.val_loss_best = val_metric_values["loss"]
                                self.val_p_acc_best = val_metric_values["policy_acc"]
                                self.val_metric_values_best = val_metric_values
                                self.k_steps_best = self.k_steps

                                if self.tc.export_weights:
                                    model_prefix = "model-%.5f-%.3f-%04d"\
                                                   % (self.val_loss_best, self.val_p_acc_best, self.k_steps_best)
                                    filepath = Path(self.tc.export_dir + f"weights/{model_prefix}.pt")
                                    # the export function saves both the architecture and the weights
                                    save_torch_state(self._model, self.optimizer, filepath)
                                    print()
                                    logging.info("Saved checkpoint to %s", filepath)

                                patience_cnt = 0  # reset the patience counter
                            # print the elapsed time
                            self.t_delta = time() - self.t_s_steps
                            print(" - %.ds" % self.t_delta)
                            self.t_s_steps = time()

                            if self.tc.log_metrics_to_tensorboard:
                                # log the samples per second metric to tensorboard
                                self.sum_writer.add_scalar(
                                    tag="samples_per_second",
                                    scalar_value=int(torch.max(data.batch)) * self.tc.batch_steps / self.t_delta,
                                    global_step=self.k_steps,
                                )

                                # log the current learning rate
                                self.sum_writer.add_scalar(tag="lr", scalar_value=self.to.lr_schedule(self.cur_it), global_step=self.k_steps)
                                # log the current momentum value
                                self.sum_writer.add_scalar(
                                    tag="momentum", scalar_value=self.to.momentum_schedule(self.cur_it), global_step=self.k_steps
                                )

                            if self.cur_it >= self.tc.total_it:
                                logging.debug("The number of given iterations has been reached")
                                # finally stop training because the number of lr drops has been achieved
                                print()
                                print(
                                    "Elapsed time for training(hh:mm:ss): "
                                    + str(datetime.timedelta(seconds=round(time() - self.t_s)))
                                )

                                if self.tc.log_metrics_to_tensorboard:
                                    self.sum_writer.close()

                                # make sure to empty cache
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()

                                return return_metrics_and_stop_training(self.k_steps, val_metric_values, self.k_steps_best,
                                                                        self.val_metric_values_best)

    def evaluate(self, train_loader):
        # log the current learning rate
        # update batch_proc_tmp counter by subtracting the batch_steps
        self.batch_proc_tmp -= self.tc.batch_steps
        ms_step = ((time() - self.t_s_steps) / self.tc.batch_steps) * 1000  # measure elapsed time
        # update the counters
        self.k_steps += 1
        self.patience_cnt += 1
        logging.info("Step %dK/%dK - %dms/step", self.k_steps, self.k_steps_end, ms_step)
        logging.info("-------------------------")
        logging.debug("Iteration %d/%d", self.cur_it, self.tc.total_it)
        logging.debug("lr: %.7f - momentum: %.7f", self.to.lr_schedule(self.cur_it),
                      self.to.momentum_schedule(self.cur_it))
        train_metric_values = evaluate_metrics(
            self.to.metrics,
            train_loader,
            self._model,
            nb_batches=25,
            ctx=self._ctx,
            sparse_policy_label=self.tc.sparse_policy_label,
            apply_select_policy_from_plane=self.tc.select_policy_from_plane and not self.tc.is_policy_from_plane_data,
            use_wdl=self.tc.use_wdl,
            use_plys_to_end=self.tc.use_plys_to_end,
        )
        val_metric_values = evaluate_metrics(
            self.to.metrics,
            self._val_loader,
            self._model,
            nb_batches=None,
            ctx=self._ctx,
            sparse_policy_label=self.tc.sparse_policy_label,
            apply_select_policy_from_plane=self.tc.select_policy_from_plane and not self.tc.is_policy_from_plane_data,
            use_wdl=self.tc.use_wdl,
            use_plys_to_end=self.tc.use_plys_to_end,
        )
        return train_metric_values, val_metric_values

    def train_update(self, batch:Batch):
        self.optimizer.zero_grad()
        batch.to(self._ctx)
        policy_out,value_out = self._model(batch.x,batch.edge_index,batch.batch)
        # policy_out = policy_out.softmax(dim=1)
        value_loss = self.value_loss(torch.flatten(value_out), batch.y)
        print(policy_out.size(),batch.policy.size())
        policy_loss = self.policy_loss(policy_out, batch.policy)
        # weight the components of the combined loss
        combined_loss = (
                self.tc.val_loss_factor * value_loss + self.tc.policy_loss_factor * policy_loss
        )
        combined_loss.backward()
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = self.to.lr_schedule(self.cur_it)  # update the learning rate
            if 'momentum' in param_group:
                param_group['momentum'] = self.to.momentum_schedule(self.cur_it)  # update the momentum
        self.optimizer.step()
        self.cur_it += 1
        self.batch_proc_tmp += 1
        return batch

    def _log_metrics(self, metric_values, global_step, prefix="train_"):
        """
        Logs a dictionary object of metric value to the console and to tensorboard
        if _log_metrics_to_tensorboard is set to true
        :param metric_values: Dictionary object storing the current metrics
        :param global_step: X-Position point of all metric entries
        :param prefix: Used for labelling the metrics
        :return:
        """
        for name in metric_values.keys():  # show the metric stats
            print(" - %s%s: %.4f" % (prefix, name, metric_values[name]), end="")
            # add the metrics to the tensorboard event file
            if self.tc.log_metrics_to_tensorboard:
                self.sum_writer.add_scalar(tag="lr", scalar_value=self.to.lr_schedule(self.cur_it),
                                           global_step=self.k_steps)

                self.sum_writer.add_scalar(tag=f'{name}/{prefix.replace("_", "")}', scalar_value=metric_values[name], global_step=global_step)

    def _setup_variables(self, cur_it):
        if self.tc.seed is not None:
            random.seed(self.tc.seed)
        # define and initialize the variables which will be used
        self.t_s = time()
        # track on how many batches have been processed in this epoch
        self.patience_cnt = self.epoch = self.batch_proc_tmp = 0
        self.k_steps = self.tc.k_steps_initial  # counter for thousands steps
        if cur_it is None:
            self.cur_it = self.tc.k_steps_initial * 1000
        else:
            self.cur_it = cur_it
        self.nb_spikes = 0  # count the number of spikes that have been detected
        # initialize the loss to compare with, with a very high value
        self.old_val_loss = 9000
        self.graph_exported = False  # create a state variable to check if the net architecture has been reported yet
        self.continue_training = True
        self.optimizer.lr = self.to.lr_schedule(self.cur_it)
        if self.tc.optimizer_name == "nag":
            self.optimizer.momentum = self.to.momentum_schedule(self.cur_it)
        if not self.ordering:  # safety check to prevent eternal loop
            raise Exception("You must have at least one part file in your planes-dataset directory!")
        if self.use_rtpt:
            # Start the RTPT tracking
            self.rtpt.start()


def create_optimizer(model: nn.Module, train_config: TrainConfig):
    if train_config.optimizer_name == "nag":  # torch.optim.SGD uses Nestorov momentum already
        return torch.optim.SGD(model.parameters(), lr=train_config.max_lr, momentum=train_config.max_momentum,
                               weight_decay=train_config.wd)
    elif train_config.optimizer_name == "adam":
        return torch.optim.Adam(model.parameters(), lr=train_config.max_lr, weight_decay=train_config.wd)
    raise Exception(f"Selected optimizer {train_config.optimizer_name} is not supported.")


class SoftCrossEntropyLoss(_Loss):
    """
    Computes cross entropy loss for continuous target distribution.
    # https://discuss.pytorch.org/t/how-should-i-implement-cross-entropy-loss-with-continuous-target-outputs/10720/18
    # or use BCELoss
    """
    def __init__(self, size_average=None, reduce=None, reduction: str = 'mean') -> None:
        super(SoftCrossEntropyLoss, self).__init__(size_average, reduce, reduction)

    def forward(self, input: Tensor, target: Tensor) -> Tensor:
        # The input is already log softmax
        return torch.sum(-target * input)


def get_context(context: str, device_id: int):
    """
    Returns the computation context as  Pytorch device object.
    :param context: Computational context either "gpu" or "cpu"
    :param device_id: Device index to use (only relevant for context=="gpu")
    :return: Pytorch device object
    """
    if context == "gpu":
        if torch.cuda.is_available():
            return torch.device(f"cuda:{device_id}")
        logging.info("No cuda device available. Fallback to CPU")
        raise ValueError("No GPU found")
    else:
        return torch.device("cpu")


def load_torch_state(model: nn.Module, optimizer: Optimizer, path: str, device_id: int):
    checkpoint = torch.load(path, map_location=f"cuda:{device_id}")
    model.load_state_dict(checkpoint['model_state_dict'])
    print(type(checkpoint['optimizer_state_dict']),checkpoint['optimizer_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])


def save_torch_state(model: nn.Module, optimizer: Optimizer, path):
    torch.save({
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
    }, path)


def export_model(model, dir=Path('.'), torch_cpu=True, torch_cuda=True):
    """
    Exports the model in ONNX and Torch Script Module.

    :param model: Pytorch model
    :param batch_sizes: List of batch sizes to use for export
    :param input_shape: Input shape of the model
    :param dir: The base path for all models
    :param torch_cpu: Whether to export as script module with cpu inputs
    :param torch_cuda: Whether to export as script module with cuda inputs
    :param onnx: Whether to export as onnx
    :param verbose: Print debug information
    """

    if dir.exists():
        # make sure that all the content is deleted first so we don't run into strange caching issues
        dir.rm_dir(dir, keep_empty_dir=False)

    dir.mkdir(parents=True, exist_ok=False)

    cpu_dir = dir / "torch_cpu"
    if torch_cpu:
        cpu_dir.mkdir(parents=True, exist_ok=False)

    torch_cuda = torch_cuda and torch.cuda.is_available()
    cuda_dir = dir / "torch_cuda"
    if torch_cuda:
        cuda_dir.mkdir(parents=True, exist_ok=False)

    model = model.eval()

    if torch_cpu:
        model = model.cpu()
        export_as_script_module(model, cpu_dir)

    if torch_cuda:
        model = model.cuda()
        export_as_script_module(model, cuda_dir)



def export_as_script_module(model, path) -> None:
    """
    Exports the model to a Torch Script Module to allow later import in C++.

    :param model: Pytorch model
    :param batch_size: The batch size of the input
    :param dummy_input: Dummy input which defines the input shape for the model
    :return:
    """

    traced = torch.jit.script(model)
    # generate a torch.jit.ScriptModule via tracing.
    # traced_script_module = torch.jit.trace(model, dummy_input)

    # serialize script module to file
    traced.save(path)


def reset_metrics(metrics):
    """
    Resets all metric entries in a dictionary object
    :param metrics:
    :return:
    """
    for metric in metrics.values():
        metric.reset()


def evaluate_metrics(metrics, data_iterator, model, nb_batches, ctx, sparse_policy_label=False,
                     apply_select_policy_from_plane=True, use_wdl=False, use_plys_to_end=False):
    """
    Runs inference of the network on a data_iterator object and evaluates the given metrics.
    The metric results are returned as a dictionary object.

    :param metrics: List of mxnet metrics which must have the
    names ['value_loss', 'policy_loss', 'value_acc_sign', 'policy_acc']
    :param data_iterator: Pytorch data iterator object
    :param model: Pytorch model handle
    :param nb_batches: Number of batches to evaluate (early stopping).
     If set to None all batches of the data_iterator will be evaluated
    :param ctx: Pytorch data context
    :param sparse_policy_label: Should be set to true if the policy uses one-hot encoded targets
     (e.g. supervised learning)
    :param apply_select_policy_from_plane: If true, given policy label is converted to policy map index
    :return:
    """
    reset_metrics(metrics)
    model.eval()  # set model to evaluation mode
    with torch.no_grad():  # operations inside don't track history
        for i, batch in enumerate(data_iterator):
            batch.to(ctx)

            policy_out,value_out = model(batch.x,batch.edge_index,batch.batch)

            # update the metrics
            metrics["value_loss"].update(preds=torch.flatten(value_out), labels=batch.y)
            metrics["policy_loss"].update(preds=policy_out, #.softmax(dim=1),
                                          labels=batch.policy)
            metrics["value_acc_sign"].update(preds=torch.flatten(value_out), labels=batch.y)
            metrics["policy_acc"].update(preds=policy_out,
                                         labels=batch.policy,
                                         graph_indices=batch.batch)

            # stop after evaluating x batches (only recommended to use this for the train set evaluation)
            if nb_batches and i+1 == nb_batches:
                break

    metric_values = {"loss": 0.01 * metrics["value_loss"].compute() + 0.99 * metrics["policy_loss"].compute()}

    for metric_name in metrics:
        metric_values[metric_name] = metrics[metric_name].compute()
    model.train()  # return back to training mode
    return metric_values

def return_metrics_and_stop_training(k_steps, val_metric_values, k_steps_best, val_metric_values_best):
    return (k_steps,
            val_metric_values["value_loss"], val_metric_values["policy_loss"],
            val_metric_values["value_acc_sign"], val_metric_values["policy_acc"]), \
           (k_steps_best, val_metric_values_best)