# CR_AHD
## Advanced Methods for Optimization - Pickup and Delivery Problem with Dynamic Time Window Assignment

### Setup
To run the code, create an environment by running 
`conda env create -f environment.yml`
Then, activate the environment, using
`conda activate AMO`

Make sure the path in [main.py at line 22](https://github.com/selting/AMO/blob/6d8974eda757f6e003ff0e0c8165f9d10145c99c/cr_ahd%20-%20Python/src/cr_ahd/main.py#L22) is correct and points to the directory of input data.
From [line 25](https://github.com/selting/AMO/blob/6d8974eda757f6e003ff0e0c8165f9d10145c99c/cr_ahd%20-%20Python/src/cr_ahd/main.py#L25) to 28, a specific or a random file can be selected if desired. Currently, all files are solved using the slicing operator `[:]`.

### Solving
Running main.py will solve all specified files using the parameters set in [`param_gen.py`](https://github.com/selting/AMO/blob/master/cr_ahd%20-%20Python/src/cr_ahd/solver_module/param_gen.py) by creating a [Solver](https://github.com/selting/AMO/blob/master/cr_ahd%20-%20Python/src/cr_ahd/solver_module/solver.py) that is defining the flow of solving steps. 

Much work is done by these three classes: Instance, CAHDSolution and Tour, which are all located in the [core module](https://github.com/selting/AMO/tree/master/cr_ahd%20-%20Python/src/cr_ahd/core_module)

Moreover, the routing logic, including tour construction, metaheuristics and neighborhoods is located in the [routing module](https://github.com/selting/AMO/tree/master/cr_ahd%20-%20Python/src/cr_ahd/routing_module)

### Output
Finally, the output will be stored in `data/Output`. This will contain log files, plotly images and the actual solutions (and a summary of them) in the `3carriers` subdirectory.
