import logging
import random
import time
from abc import abstractmethod, ABC
from copy import deepcopy
from math import exp, log
from typing import Sequence

from src.cr_ahd.core_module import instance as it, solution as slt, tour as tr
from src.cr_ahd.routing_module import neighborhoods as nh, shakes as sh, tour_construction as cns
from src.cr_ahd.utility_module import utils as ut, profiling as pr

logger = logging.getLogger(__name__)

TIME_MAX = float(10)  # 0.05 is roughly the time required by the VND procedure to exhaust all neighborhoods


class PDPTWMetaHeuristic(ABC):
    def __init__(self, neighborhoods: Sequence[nh.Neighborhood]):
        self.neighborhoods = neighborhoods
        self.improved = False
        self.start_time = None
        self.parameters = dict()
        self.history = []  # collection of e.g. visited neighbors, accepted moves, ...
        self.trajectory = []  # collection of all accepted & executed moves

        self.name = f'{self.__class__.__name__}{[n.__class__.__name__ for n in self.neighborhoods]}'

    @abstractmethod
    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        pass

    @abstractmethod
    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        return True

    # @abstractmethod
    def change_neighborhood(self):
        pass

    @abstractmethod
    def stopping_criterion(self):
        pass

    def update_parameters(self, move: tuple, accepted: bool):
        pass

    def is_move_tabu(self, move: tuple):
        return False

    def update_history(self, k, move, accepted):
        self.history.append((self.neighborhoods[k].__name__, move, accepted))
        pass


class NoMetaheuristic(PDPTWMetaHeuristic):
    """Placeholder for cases in which no improvement is wanted"""

    def stopping_criterion(self):
        pass

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        pass

    def execute(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        return solution


# class PDPTWIntraTourMetaheuristic(PDPTWMetaHeuristic, ABC):
#     """Metaheuristic that operates only on a single tour, i.e. all its neighborhoods are IntraTourNeighborhood"""
#     def __init__(self, neighborhoods: Sequence[nh.Neighborhood]):
#         for nbh in neighborhoods:
#             assert isinstance(nbh, nh.IntraTourNeighborhood)
#         super().__init__(neighborhoods)
#
#     @abstractmethod
#     def execute(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
#         pass
#
#     @abstractmethod
#     def execute_on_tour(self, instance:it.PDPInstance, solution:slt.CAHDSolution, tour_=tr.Tour):
#         pass

class LocalSearchFirst(PDPTWMetaHeuristic):
    """
    local search heuristic using the first improvement strategy
    """

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        best_solution = deepcopy(original_solution)
        assert len(self.neighborhoods) == 1, 'Local Search can use a single neighborhood only!'
        if carriers is None:
            carriers = range(len(best_solution.carriers))

        for carrier in carriers:
            neighborhood = self.neighborhoods[0]
            self.improved = True
            self.start_time = time.time()
            while not self.stopping_criterion():
                self.improved = False
                move_gen = neighborhood.feasible_move_generator(instance, best_solution, carrier)
                try:
                    move = next(move_gen)  # may be feasible but not improving
                    while not self.acceptance_criterion(instance, best_solution, carrier, move):
                        move = next(move_gen)
                    neighborhood.execute_move(instance, best_solution, move)
                    self.trajectory.append(move)
                    self.improved = True
                except StopIteration:
                    break  # exit the while loop (while-condition is false anyway)
        return best_solution

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        if move[0] < 0:
            return True
        else:
            return False

    def stopping_criterion(self):
        if self.improved and time.time() - self.start_time < TIME_MAX:
            return False
        else:
            return True


class LocalSearchBest(PDPTWMetaHeuristic):
    """implements a the local search heuristic using the best improvement strategy, i.e. steepest descent"""

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        best_solution = deepcopy(original_solution)
        assert len(self.neighborhoods) == 1, 'Local Search must have a single neighborhood only!'
        if carriers is None:
            carriers = range(len(best_solution.carriers))

        for carrier in carriers:
            neighborhood = self.neighborhoods[0]
            self.improved = True
            self.start_time = time.time()
            while not self.stopping_criterion():
                self.improved = False
                all_moves = [move for move in neighborhood.feasible_move_generator(instance, best_solution, carrier)]
                if any(all_moves):
                    best_move = min(all_moves, key=lambda x: x[0])
                    if self.acceptance_criterion(instance, best_solution, carrier, best_move):
                        neighborhood.execute_move(instance, best_solution, best_move)
                        self.trajectory.append(best_move)
                        self.improved = True
        return best_solution

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        if move[0] < 0:
            return True
        else:
            return False

    def stopping_criterion(self):
        if self.improved and time.time() - self.start_time < TIME_MAX:
            return False
        else:
            return True


class PDPTWSequentialLocalSearch(PDPTWMetaHeuristic):
    """
    Sequentially exhaust each neighborhood in their given order. Only improvements are accepted. First improvement is
    used.
    """

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        best_solution = deepcopy(original_solution)
        if carriers is None:
            carriers = range(len(best_solution.carriers))

        for carrier in carriers:
            for k in range(len(self.neighborhoods)):
                neighborhood = self.neighborhoods[k]
                move_generator = neighborhood.feasible_move_generator(instance, best_solution, carrier)
                self.start_time = time.time()
                self.improved = True
                while not self.stopping_criterion():
                    self.improved = False
                    accepted = False
                    while accepted is False:
                        try:
                            move = next(move_generator)
                            if self.acceptance_criterion(instance, best_solution, carrier, move):
                                accepted = True
                                neighborhood.execute_move(instance, best_solution, move)
                                self.improved = True
                                self.trajectory.append(move)
                                move_generator = neighborhood.feasible_move_generator(instance, best_solution, carrier)
                        except StopIteration:
                            # StopIteration occurs if there are no neighbors that can be returned by the move_generator
                            break
        return best_solution

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        if move is None:
            return False
        elif move[0] < 0:
            return True
        else:
            return False

    def stopping_criterion(self):
        if self.improved and time.time() - self.start_time < TIME_MAX:
            return False
        else:
            return True


class PDPTWVariableNeighborhoodDescent(PDPTWMetaHeuristic):
    """
    deterministic variant of VNS. multiple neighborhoods are ordered and searched sequentially. In each neighborhood
    that is searched, the *best* found neighbor is used. When stuck in a local optimum, switches to the next
    neighborhood
    """

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        best_solution = deepcopy(original_solution)
        if carriers is None:
            carriers = range(len(best_solution.carriers))

        for carrier in carriers:
            self.parameters['k'] = 0
            self.start_time = time.time()
            while not self.stopping_criterion():
                neighborhood = self.neighborhoods[self.parameters['k']]
                all_moves = [move for move in neighborhood.feasible_move_generator(instance, best_solution, carrier)]
                if any(all_moves):
                    best_move = min(all_moves, key=lambda x: x[0])
                    if self.acceptance_criterion(instance, best_solution, carrier, best_move):
                        neighborhood.execute_move(instance, best_solution, best_move)
                        # ut.validate_solution(instance, best_solution)
                        self.trajectory.append(best_move)
                        self.parameters['k'] = 0
                    else:
                        self.parameters['k'] += 1
                else:
                    self.parameters['k'] += 1
        return best_solution

    def execute_on_tour(self, instance: it.PDPInstance, solution: slt.CAHDSolution, tour_: tr.Tour):
        """
        execute the metaheuristic for a given route (in place) using all available intra-tour neighborhoods. useful if
        a tour shall be improved that does not belong to a carrier. E.g. when estimating the tour length of a bundle
        """

        intra_tour_neighborhoods = [nbh for nbh in self.neighborhoods if isinstance(nbh, nh.IntraTourNeighborhood)]
        k = 0
        while k < len(intra_tour_neighborhoods):
            neighborhood = intra_tour_neighborhoods[k]
            all_moves = [move for move in neighborhood.feasible_move_generator_for_tour(instance, solution, tour_)]
            if any(all_moves):
                best_move = min(all_moves, key=lambda x: x[0])
                if self.acceptance_criterion_tour(best_move):
                    neighborhood.execute_move(instance, solution, best_move)
                    self.trajectory.append(best_move)
                    k = 0
                else:
                    k += 1
            else:
                k += 1

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        if move[0] < 0:
            return True
        else:
            return False

    def acceptance_criterion_tour(self, move: tuple):
        if move[0] < 0:
            return True
        else:
            return False

    def stopping_criterion(self):
        if self.parameters['k'] < len(self.neighborhoods) and time.time() - self.start_time < TIME_MAX:
            return False
        else:
            return True


class PDPTWSimulatedAnnealing(PDPTWMetaHeuristic):
    def __init__(self, neighborhoods: Sequence[nh.Neighborhood]):
        super().__init__(neighborhoods)
        self.parameters['initial_temperature'] = 0
        self.parameters['temperature'] = 0

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        solution = deepcopy(original_solution)
        if carriers is None:
            carriers = range(len(solution.carriers))

        best_solution = solution

        for carrier in carriers:
            self.parameters['initial_temperature'] = self.compute_start_temperature(solution, carrier)
            self.parameters['temperature'] = self.parameters['initial_temperature']

            self.start_time = time.time()

            i = 0
            while not self.stopping_criterion():
                # update the current temperature
                self.parameters['temperature'] = self.parameters['initial_temperature'] * 0.85 ** i

                # random neighbor
                neighborhood = random.choice(self.neighborhoods)
                moves = list(neighborhood.feasible_move_generator(instance, solution, carrier))
                if any(moves):
                    move = random.choice(moves)

                    # always accept improving moves, accept deteriorating moves with a certain probability
                    if self.acceptance_criterion(instance, solution, carrier, move):
                        neighborhood.execute_move(instance, solution, move)
                        # update the best solution
                        if solution.sum_profit() > best_solution.sum_profit():
                            best_solution = solution
                else:
                    continue
                i += 1
        return best_solution

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        try:
            if move is None:
                return False
            # improving move is always accepted
            elif move[0] <= 0:
                return True
            # degrading move is accepted with certain probability
            elif random.random() < exp(-move[0] / self.parameters['temperature']):  # might raise OverflowError
                return True
            else:
                return False
        except OverflowError:
            # overflow caused by double limit if temperature is too low. In that case the random number will most
            # likely not be smaller than the required probability
            return False

    def stopping_criterion(self):
        if time.time() - self.start_time < TIME_MAX and self.parameters['temperature'] > 1:
            return False
        else:
            return True

    @staticmethod
    def compute_start_temperature(solution, carrier: int, start_temp_control_param=0.5):
        """compute start temperature according to Ropke,S., & Pisinger,D. (2006). An Adaptive Large Neighborhood
        Search Heuristic for the Pickup and Delivery Problem with Time Windows. Transportation Science, 40(4),
        455–472. https://doi.org/10.1287/trsc.1050.0135

        a solution that is (start_temp_control_param * 100) % worse will be accepted with a probability 0.5
        """
        carrier_ = solution.carriers[carrier]
        obj = carrier_.sum_profit()
        acceptance_probability = 0.5
        temperature = -(obj * start_temp_control_param) / log(acceptance_probability)
        return temperature


class PDPTWIteratedLocalSearch(PDPTWMetaHeuristic):
    """

    """

    def execute(self, instance: it.PDPInstance, original_solution: slt.CAHDSolution, carriers=None) -> slt.CAHDSolution:
        solution = deepcopy(original_solution)

        if carriers is None:
            carriers = range(len(solution.carriers))

        solution = self.local_search(instance, solution, carriers)
        best_solution = solution
        num_requests = 2

        for carrier in carriers:

            self.start_time = time.time()

            while not self.stopping_criterion():
                solution_1 = self.perturbation(instance, solution, carrier, num_requests)
                solution_1 = self.local_search(instance, solution_1, [carrier])
                # hacky way to define a move as (old_solution, new_solution) since describing a "move" with all
                # information of the perturbation is cumbersome
                if solution_1.sum_profit() > best_solution.sum_profit():
                    best_solution = solution_1

                if self.acceptance_criterion(instance, solution, carrier, (solution, solution_1)):
                    solution = solution_1

        return best_solution

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move: tuple):
        """
        accept slight degradations: Threshold acceptance

        :param instance:
        :param solution:
        :param carrier:
        :param move:
        :return:
        """
        solution_1: slt.CAHDSolution
        solution, solution_1 = move
        if solution.sum_profit() > solution_1.sum_profit() > solution.sum_profit() * 0.9:
            return True
        else:
            return False

    def perturbation(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, num_requests: int):
        solution_copy = deepcopy(solution)
        try:
            # destroy
            sh.RandomRemovalShake().execute(instance, solution_copy, carrier,
                                            num_requests)  # todo test different shakes
            # repair
            cns.MinTravelDistanceInsertion().insert_all(instance, solution_copy, carrier)  # todo test different repairs
            return solution_copy
        except ut.ConstraintViolationError:
            # sometimes the shaking cannot be repaired with the given method and will raise a ConstraintViolationError
            # in that case, simply returning the original solution
            return solution

    def local_search(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carriers: Sequence[int]):
        solution_copy = deepcopy(solution)
        random_neighborhood = random.choice(self.neighborhoods)  # TODO should be a parameter
        LocalSearchFirst([random_neighborhood]).execute(instance, solution_copy, carriers)
        return solution_copy

    def stopping_criterion(self):
        if time.time() - self.start_time < TIME_MAX:
            return False
        else:
            return True
