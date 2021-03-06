import logging.config
import random
from pathlib import Path
from datetime import datetime
import cProfile

from solver_module import workflow as wf
from utility_module import utils as ut, evaluation as ev, cr_ahd_logging as log
from utility_module.utils import write_solution_summary_to_multiindex_df

logging.config.dictConfig(log.LOGGING_CONFIG)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    def cr_ahd():
        # setup
        logger.info(f'START {datetime.now()}')
        random.seed()

        # select the files to be solved
        paths = sorted(
            list(Path('data/Input/').iterdir()),
            key=ut.natural_sort_key
        )
        run, rad, n = 11, 0, 1  # rad: 0->150; 1->200; 2->300 // n: 0->10; 1->15
        i = run * 6 + rad * 2 + n
        i = random.choice(range(len(paths)))
        paths = paths[:]

        # solving
        if len(paths) < 6:
            solutions = wf.solve_instances(paths)
        else:
            solutions = wf.solve_instances_multiprocessing(paths)
        df, csv_path = write_solution_summary_to_multiindex_df(solutions, 'solution')

        # plotting and evaluation
        ev.bar_chart(df,
                     title=str(csv_path.name),
                     values='sum_travel_distance',
                     color=['tour_improvement'],
                     category='tour_improvement_time_limit_per_carrier',
                     facet_col='rad',
                     facet_row='n',
                     show=True,
                     html_path=ut.unique_path(ut.output_dir, 'CAHD_#{:03d}.html').as_posix())
        secondary_parameter = 'neighborhoods'
        ev.print_top_level_stats(df, [secondary_parameter])

        logger.info(f'END {datetime.now()}')

        # send windows to sleep
        # os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


    # PROFILING
    cProfile.run('cr_ahd()', ut.output_dir.joinpath('cr_ahd_stats'))
    """
    # STATS
    p = pstats.Stats(ut.output_dir.joinpath('cr_ahd_stats').as_posix())
    # remove the extraneous path from all the module names:
    p.strip_dirs()
    # sorts the profile by cumulative time in a function, and then only prints the n most significant lines:
    p.sort_stats('cumtime').print_stats(50)
    # see what functions were looping a lot, and taking a lot of time:
    p.sort_stats('tottime').print_stats(20)
    p.sort_stats('ncalls').print_stats(20)
    # p.print_callers(20)
    """
