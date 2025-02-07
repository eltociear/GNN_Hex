"""
@file: train_config.py
Created on 01.11.19
@project: CrazyAra
@author: queensgambit

Training configuration file
"""
from dataclasses import dataclass
from torch_geometric.nn.norm import LayerNorm


@dataclass
class TrainConfig:
    """Class which stores all training configuration"""

    # div factor is a constant which can be used to reduce the batch size and learning rate respectively
    # use a value higher 1 if you encounter memory allocation errors
    div_factor: int = 1

    # 1024 # the batch_size needed to be reduced to 1024 in order to fit in the GPU 1080Ti
    # 4096 was originally used in the paper -> works slower for current GPU
    # 2048 was used in the paper Mastering the game of Go without human knowledge and fits in GPU memory
    # typically if you half the batch_size you should double the lr
    batch_size: int = int(1024 / div_factor)
    # batch_size = 10

    # batch_steps = 1000 means for example that every 1000 batches the validation set gets processed
    # this defines how often a new checkpoint will be saved and the metrics evaluated
    batch_steps: int = 100 * div_factor

    # set the context on CPU switch to GPU if there is one available (strongly recommended for training)
    context: str = "gpu"

    cpu_count: int = 1  # increasing above 1 may result in shared memory error

    device_id: int = 0

    discount: float = 1.0

    dropout_rate: float = 0

    # directory to write and read weight, log, onnx and other export files
    export_dir: str = "./"

    export_weights: bool = True

    export_grad_histograms: bool = True

    # Decide between 'pytorch', 'mxnet' and 'gluon' style for training
    # Reinforcement Learning only works with gluon and pytorch atm
    framework: str = 'pytorch'

    # Boolean if the policy data is also defined in select_policy_from_plane representation
    is_policy_from_plane_data: bool = False

    log_metrics_to_tensorboard: bool = True

    # these are the weights to continue training with
    # symbol_file = 'model_init-symbol.json' # model-1.19246-0.603-symbol.json'
    # params_file = 'model_init-0000.params' # model-1.19246-0.603-0223.params'
    symbol_file: str = ''
    params_file: str = ''

    # # optimization parameters
    optimizer_name: str = "adam"
    lr: float = 0.001
    max_momentum: float = 0.95
    min_momentum: float = 0.8
    # stop training as soon as max_spikes has been reached
    max_spikes: int = 20

    # name initials which are used to identify running training processes with rtpt
    # prefix for the process name in order to identify the process on a server
    name_initials: str = "YK"

    nb_parts: int = None

    # how many epochs the network will be trained each time there is enough new data available
    nb_training_epochs: int = 200

    training_keep_files: int = 40

    # policy_loss_factor: float = 1  # 0.99
    policy_loss_factor = 1

    # gradient scaling for the plys to end output
    plys_to_end_loss_factor: float = 0.1

    # ratio for mixing the value return with the corresponding q-value
    # for a ratio of 0 no q-value information will be used
    q_value_ratio: float = 0.15
    # q_value_ratio: float = 0

    # set a specific seed value for reproducibility
    seed: int = 42

    # Boolean if potential legal moves will be selected from final policy output
    select_policy_from_plane: bool = True

    # define spike threshold when the detection will be triggered
    spike_thresh: float = 1.5

    # Boolean if the policy target is one-hot encoded (sparse=True) or a target distribution (sparse=False)
    sparse_policy_label: bool = False

    # adds a small mlp to infer the value loss from wdl and plys_to_end_output
    use_mlp_wdl_ply: bool = False
    # enables training with ply to end head
    use_plys_to_end: bool = False
    # enables training with a wdl head as intermediate target (mainly useful for environments with 3 outcomes)
    use_wdl: bool = False

    # loads a previous checkpoint if the loss increased significantly
    use_spike_recovery: bool = False
    # weight the value loss a lot lower than the policy loss in order to prevent overfitting
    val_loss_factor: float = 1  # 1 changed
    # weight for the wdl loss
    wdl_loss_factor: float = 0.4

    # weight decay
    wd: float = 1e-4

    net_type = "SAGE"
    hidden_channels = 60
    hidden_layers = 15
    policy_layers = 2
    value_layers = 2
    in_channels = 3
    swap_allowed = False
    norm = None
    # @staticmethod
    # def norm(hc):
    #     LayerNorm(hc,mode="node")
    # norm = LayerNorm

@dataclass
class TrainObjects:
    """Defines training objects which must be set before the training"""
    metrics = None
    variant_metrics = None

