#include "tests/speedtest.cpp"
#include "tests/test_env.cpp"
#include "tests/consistency_test.cpp"
#include "tests/test_my_graph.cpp"
#include "tests/test_torch_script.cpp"
#include "tests/test_copy.cpp"

int main(int argc, char * argv[]){
	assert (argc>1);
	if (string(argv[1]).compare("interactive")==0){
		interactive_env();
	}
	else if (string(argv[1]).compare("speedtest")==0){
		speedtest();
	}
	else if (string(argv[1]).compare("consistency")==0){
		test_dead_and_captured_consistency();
	}
	else if (string(argv[1]).compare("graph")==0){
		play_around_with_graph();
	}
	else if (string(argv[1]).compare("copy")==0){
		test_copy();
	}
	else if (string(argv[1]).compare("torch_script")==0){
		assert (argc>2);
		test_torch_script(argv[2]);
	}
	else{
		throw runtime_error("Error: Invalid argument "+string(argv[1]));
	}
}
