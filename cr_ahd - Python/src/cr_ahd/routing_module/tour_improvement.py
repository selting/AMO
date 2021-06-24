import logging
from abc import ABC, abstractmethod
from typing import final

from src.cr_ahd.core_module import instance as it, solution as slt, tour as tr

logger = logging.getLogger(__name__)


# TODO implement a best-improvement vs first-improvement mechanism on the parent-class level. e.g. as a self.best:bool
class LocalSearchBehavior(ABC):

    def local_search(self, instance: it.PDPInstance, solution: slt.CAHDSolution,
                     best_improvement: bool = False):
        for carrier in range(instance.num_carriers):
            self.improve_carrier_solution(instance, solution, carrier, best_improvement)
        pass

    @abstractmethod
    def improve_carrier_solution(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int,
                                 best_improvement: bool):
        pass


'''
class PDPGradientDescent(TourImprovementBehavior):
    """
    As a the most basic "metaheuristic". Whether or not solutions are accepted should then happen on this level. Here:
    always accept only improving solutions
    """

    def local_search(self, instance: it.PDPInstance, solution: slt.GlobalSolution):
        pass

    def improve_carrier_solution(self, instance: it.PDPInstance, solution: slt.GlobalSolution, carrier: int):
        pass

    def acceptance_criterion(self, instance: it.PDPInstance, solution: slt.GlobalSolution, carrier: int, delta,
                             history):
        pass
'''


# =====================================================================================================================
# INTRA-TOUR LOCAL SEARCH
# =====================================================================================================================


class PDPIntraTourLocalSearch(LocalSearchBehavior, ABC):

    @final
    def improve_carrier_solution(self,
                                 instance: it.PDPInstance,
                                 solution: slt.CAHDSolution,
                                 carrier: int,
                                 best_improvement: bool):
        for tour in range(solution.carriers[carrier].num_tours()):
            self.improve_tour(instance, solution, carrier, tour, best_improvement)
        pass

    def improve_tour(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int,
                     best_improvement: bool):
        """
        :param best_improvement: whether to follow a first improvement strategy (False, default) or a best improvement
        (True) strategy

        finds and executes local search moves as long as they yield an improvement.


        """
        improved = True
        while improved:
            improved = False
            move = self.find_feasible_move(instance, solution, carrier, tour, best_improvement)

            # the first element of a move tuple is always its delta
            if self.acceptance_criterion(move[0]):
                logger.debug(f'Intra Tour Local Search move found:')
                self.execute_move(instance, solution, carrier, tour, move)
                improved = True

    @abstractmethod
    def find_feasible_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int,
                           best_improvement: bool):
        """
        :param best_improvement: False (default) if the FIRST improving move shall be executed; True if the BEST
        improving move shall be executed

        :return: tuple containing all necessary information to see whether to accept a move and the information to
        execute a move. The first element must be the delta.
        """
        pass

    def acceptance_criterion(self, delta):  # acceptance criteria could even be their own class
        if delta < 0:
            return True
        else:
            return False

    @abstractmethod
    def execute_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        pass

    @abstractmethod
    def feasibility_check(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        pass


class PDPMove(PDPIntraTourLocalSearch, ABC):
    """
    Take a PD pair and see whether inserting it in a different location of the SAME route improves the solution
    """

    def find_feasible_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int,
                           best_improvement: bool):
        tour_ = solution.carriers[carrier].tours[tour]

        # initialize the best known solution
        best_delta = 0
        best_pickup = None
        best_delivery = None
        best_new_pickup_pos = None
        best_new_delivery_pos = None
        best_move = (best_delta, best_pickup, best_delivery, best_new_pickup_pos, best_new_delivery_pos)

        # test all requests
        for old_pickup_pos in range(1, len(tour_) - 2):
            vertex = tour_.routing_sequence[old_pickup_pos]

            # skip if its a delivery vertex
            if instance.vertex_type(vertex) == "delivery":
                continue

            pickup, delivery = instance.pickup_delivery_pair(instance.request_from_vertex(vertex))
            old_delivery_pos = tour_.routing_sequence.index(delivery)

            delta = 0

            # savings of removing request vertices from their current positions
            for old_pos in (old_delivery_pos, old_pickup_pos):
                predecessor = tour_.routing_sequence[old_pos - 1]
                vertex = tour_.routing_sequence[old_pos]
                successor = tour_.routing_sequence[old_pos + 1]
                delta -= instance.distance([predecessor, vertex], [vertex, successor])
                delta += instance.distance([predecessor], [successor])

            # pop
            tour_.pop_and_update(instance, solution, (old_pickup_pos, old_delivery_pos))

            # check all possible new insertions for pickup and delivery vertex of the request
            for new_pickup_pos in range(1, len(tour_) - 2):
                for new_delivery_pos in range(new_pickup_pos + 1, len(tour_) - 1):
                    if new_pickup_pos == old_pickup_pos and new_delivery_pos == old_delivery_pos:
                        continue

                    # cost for inserting request vertices in the new positions
                    insertion_shift = 0
                    for vertex, new_pos in zip((pickup, delivery), (new_pickup_pos, new_delivery_pos)):
                        predecessor = tour_.routing_sequence[new_pos - 1 + insertion_shift]
                        successor = tour_.routing_sequence[new_pos + insertion_shift]
                        delta += instance.distance([predecessor, vertex], [vertex, successor])
                        delta -= instance.distance([predecessor], [successor])
                        insertion_shift += 1

                    # is the current move an improvement?
                    if delta < best_delta:
                        move = (delta, pickup, delivery, new_pickup_pos, new_delivery_pos)

                        # is the improving move feasible?
                        if self.feasibility_check(instance, solution, carrier, tour, move):

                            best_move = move

                            # first improvement: repair & return the move
                            if not best_improvement:
                                tour_.insert_and_update(instance,
                                                        solution,
                                                        (old_pickup_pos, old_delivery_pos),
                                                        (pickup, delivery))
                                return move

                            # best improvement: update the best known solution and continue
                            else:
                                best_delta = delta


            # repair
            tour_.insert_and_update(instance, solution, (old_pickup_pos, old_delivery_pos), (pickup, delivery))

        # if best improvement (or no improvement was found), return best move
        return best_move

    def feasibility_check(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        """
        receives a destroyed tour in which a certain request has been removed. Checks insertion at another place
        """

        delta, pickup_vertex, delivery_vertex, new_pickup_pos, new_delivery_pos = move
        assert delta < 0, f'Move is non-improving'
        assert delivery_vertex == pickup_vertex + instance.num_requests
        tour_ = solution.carriers[carrier].tours[tour]

        return tour_.insertion_feasibility_check(instance, solution, [new_pickup_pos, new_delivery_pos],
                                                 [pickup_vertex, delivery_vertex])

    def execute_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        delta, pickup_vertex, delivery_vertex, new_pickup_pos, new_delivery_pos = move
        tour_ = solution.carriers[carrier].tours[tour]

        tour_.insert_and_update(instance, solution, [new_pickup_pos, new_delivery_pos],
                                [pickup_vertex, delivery_vertex])


class PDPTwoOpt(PDPIntraTourLocalSearch):
    def find_feasible_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int,
                           best_improvement: bool):
        tour_ = solution.carriers[carrier].tours[tour]

        # initialize the best known solution
        best_pos_i = None
        best_pos_j = None
        best_delta = 0
        best_move = (best_delta, best_pos_i, best_pos_j)

        # iterate over all moves
        for i in range(0, len(tour_) - 3):
            for j in range(i + 2, len(tour_) - 1):

                delta = 0

                # savings of removing the edges (i, i+1) and (j, j+1)
                delta -= instance.distance([tour_.routing_sequence[i], tour_.routing_sequence[j]],
                                           [tour_.routing_sequence[i + 1], tour_.routing_sequence[j + 1]])

                # cost of adding the edges (i, j) and (i+1, j+1)
                delta += instance.distance([tour_.routing_sequence[i], tour_.routing_sequence[i + 1]],
                                           [tour_.routing_sequence[j], tour_.routing_sequence[j + 1]])

                # is the current move an improvement?
                if delta < best_delta:
                    move = (delta, i, j)

                    # is the improving move feasible?
                    if self.feasibility_check(instance, solution, carrier, tour, move):

                        # best improvement: update the best known solution and continue
                        if best_improvement:
                            best_delta = delta
                            best_move = move

                        # first improvement: return the move
                        else:
                            return move

        return best_move

    def feasibility_check(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        delta, i, j = move
        assert delta < 0, f'Move is non-improving'
        tour_ = solution.carriers[carrier].tours[tour]

        # create a temporary routing sequence to loop over the one that contains the reversed section
        tmp_routing_sequence = list(tour_.routing_sequence)
        pop_indices = [x for x in tmp_routing_sequence[i:j]]
        popped, _ = tr.multi_pop_and_update(routing_sequence=tmp_routing_sequence,
                                            sum_travel_distance=tour_.sum_travel_distance,
                                            sum_travel_duration=tour_.sum_travel_duration,
                                            arrival_schedule=tour_.arrival_schedule,
                                            service_schedule=tour_.service_schedule,
                                            sum_load=tour_.sum_load,
                                            sum_revenue=tour_.sum_revenue,
                                            sum_profit=tour_.sum_profit,
                                            wait_sequence=tour_.wait_sequence,
                                            max_shift_sequence=tour_.max_shift_sequence,
                                            distance_matrix=instance._distance_matrix,
                                            vertex_load=instance.load,
                                            revenue=instance.revenue,
                                            service_duration=instance.service_duration,
                                            tw_open=solution.tw_open,
                                            tw_close=solution.tw_close,
                                            pop_indices=pop_indices)

        return tr.multi_insertion_feasibility_check(
            routing_sequence=tour_.routing_sequence,
            sum_travel_distance=tour_.sum_travel_distance,
            sum_travel_duration=tour_.sum_travel_duration,
            arrival_schedule=tour_.arrival_schedule,
            service_schedule=tour_.service_schedule,
            sum_load=tour_.sum_load,
            sum_revenue=tour_.sum_revenue,
            sum_profit=tour_.sum_profit,
            wait_sequence=tour_.wait_sequence,
            max_shift_sequence=tour_.max_shift_sequence,
            num_depots=instance.num_depots,
            num_requests=instance.num_requests,
            distance_matrix=instance._distance_matrix,
            vertex_load=instance.load,
            revenue=instance.revenue,
            service_duration=instance.service_duration,
            vehicles_max_travel_distance=instance.vehicles_max_travel_distance,
            vehicles_max_load=instance.vehicles_max_load,
            tw_open=solution.tw_open,
            tw_close=solution.tw_close,
            insertion_indices=range(i, j),
            insertion_vertices=reversed(popped),

        )

    def execute_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, tour: int, move):
        _, i, j = move
        solution.carriers[carrier].tours[tour].reverse_section(instance, solution, i, j)


# =====================================================================================================================
# INTER-TOUR LOCAL SEARCH
# =====================================================================================================================


class PDPInterTourLocalSearch(LocalSearchBehavior):
    @final
    def improve_carrier_solution(self, instance: it.PDPInstance, solution: slt.CAHDSolution,
                                 carrier: int, best_improvement: bool):
        improved = True
        while improved:
            improved = False
            move = self.find_feasible_move(instance, solution, carrier, best_improvement)

            # the first element of a move tuple is always its delta
            if self.acceptance_criterion(move[0]):
                logger.debug(f'Inter Tour Local Search move found:')
                self.execute_move(instance, solution, carrier, move)
                improved = True

        pass

    @abstractmethod
    def find_feasible_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int,
                           best_improvement: bool):
        """
        :param best_improvement: False (default) if the FIRST improving move shall be executed; True if the BEST
        improving move shall be executed

        :return: tuple containing all necessary information to see whether to accept a move and the information to
        execute a move. The first element must be the delta.
        """
        pass

    def acceptance_criterion(self, delta):  # acceptance criteria could even be their own class
        if delta < 0:
            return True
        else:
            return False

    @abstractmethod
    def execute_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move):
        pass

    @abstractmethod
    def feasibility_check(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move):
        pass


class PDPRelocate(PDPInterTourLocalSearch):
    """
    Take one PD request at a time and see whether inserting it into another tour is cheaper.
    """

    def find_feasible_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int,
                           best_improvement: bool):
        carrier_ = solution.carriers[carrier]

        # initialize the best known solution
        best_delta = 0
        best_old_tour = None
        best_old_pickup_pos = None
        best_old_delivery_pos = None
        best_new_tour = None
        best_new_pickup_pos = None
        best_new_delivery_pos = None
        best_move = (
            best_delta, best_old_tour, best_old_pickup_pos, best_old_delivery_pos, best_new_tour, best_new_pickup_pos,
            best_new_delivery_pos)

        for old_tour in range(carrier_.num_tours()):

            # check all requests of the old tour
            # a pickup can be at most at index n-2 (n is depot, n-1 must be delivery)
            for old_pickup_pos in range(1, len(carrier_.tours[old_tour]) - 2):
                vertex = carrier_.tours[old_tour].routing_sequence[old_pickup_pos]

                # skip if its a delivery vertex
                if instance.vertex_type(vertex) == "delivery":
                    continue  # skip if its a delivery vertex

                pickup, delivery = instance.pickup_delivery_pair(instance.request_from_vertex(vertex))
                old_delivery_pos = carrier_.tours[old_tour].routing_sequence.index(delivery)

                pickup_predecessor = carrier_.tours[old_tour].routing_sequence[old_pickup_pos - 1]
                pickup_successor = carrier_.tours[old_tour].routing_sequence[old_pickup_pos + 1]
                delivery_predecessor = carrier_.tours[old_tour].routing_sequence[old_delivery_pos - 1]
                delivery_successor = carrier_.tours[old_tour].routing_sequence[old_delivery_pos + 1]

                delta = 0

                # differentiate between cases were
                # (a) pickup and delivery are in immediate succession ...
                if delivery_predecessor == pickup:

                    # savings of removing request from current tour
                    delta -= instance.distance([pickup_predecessor, pickup, delivery],
                                               [pickup, delivery, delivery_successor])

                    # cost of reconnecting the lose ends
                    delta += instance.distance([pickup_predecessor], [delivery_successor])

                # ... or (b) there are other vertices between pickup and delivery
                else:

                    # savings of removing request from current tour
                    delta -= instance.distance([pickup_predecessor, pickup, delivery_predecessor, delivery],
                                               [pickup, pickup_successor, delivery, delivery_successor])

                    # cost of reconnecting the lose ends
                    delta += instance.distance([pickup_predecessor, delivery_predecessor],
                                               [pickup_successor, delivery_successor])

                # cost for inserting request into another tour
                # check all new tours
                for new_tour in range(carrier_.num_tours()):
                    new_tour_ = carrier_.tours[new_tour]

                    # skip the current tour, there is the PDPMove local search for that option
                    if new_tour == old_tour:
                        continue

                    # check all possible new insertions for pickup and delivery vertex of the request
                    for new_pickup_pos in range(1, len(new_tour_) - 1):
                        for new_delivery_pos in range(new_pickup_pos + 1, len(new_tour_)):
                            delta += new_tour_.single_insertion_distance_delta(
                                instance, [new_pickup_pos, new_delivery_pos], [pickup, delivery])

                            # is the current move an improvement?
                            if delta < best_delta:
                                move = (delta, old_tour, old_pickup_pos, old_delivery_pos, new_tour, new_pickup_pos,
                                        new_delivery_pos)

                                # is the improving move feasible?
                                if self.feasibility_check(instance, solution, carrier, move):

                                    # best improvement: update the best known solution and continue
                                    if best_improvement:
                                        best_delta = delta
                                        best_move = move

                                    # first improvement: return the move
                                    else:
                                        return move

        return best_move

    def feasibility_check(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move):
        delta, old_tour, old_pickup_pos, old_delivery_pos, new_tour, new_pickup_pos, new_delivery_pos = move
        assert delta < 0, f'Move is non-improving'
        old_tour_ = solution.carriers[carrier].tours[old_tour]
        new_tour_ = solution.carriers[carrier].tours[new_tour]

        # create a temporary copy of the routing sequence to check feasibility
        tmp_routing_sequence = list(new_tour_.routing_sequence)
        pickup = old_tour_.routing_sequence[old_pickup_pos]
        delivery = old_tour_.routing_sequence[old_delivery_pos]
        tmp_routing_sequence.insert(new_pickup_pos, pickup)
        tmp_routing_sequence.insert(new_delivery_pos, delivery)

        # find the index from which constraints must be checked
        check_from_index = new_pickup_pos

        return tr.feasibility_check(instance, solution, carrier, new_tour, tmp_routing_sequence, check_from_index)

    def execute_move(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, move):
        delta, old_tour, old_pickup_pos, old_delivery_pos, new_tour, new_pickup_pos, new_delivery_pos = move
        carrier_ = solution.carriers[carrier]

        (pickup, delivery), _ = carrier_.tours[old_tour].pop_and_update(instance, solution,
                                                                        [old_pickup_pos, old_delivery_pos])

        # if it is now empty (i.e. depot -> depot), drop the old tour
        if len(carrier_.tours[old_tour]) <= 2:
            carrier_.tours.pop(old_tour)
            # TODO must I update the tour.id_ ensure that there is no gap in the tour's ids? Nah, don't think so

        carrier_.tours[new_tour].multi_insert_and_update(instance, solution, [new_pickup_pos, new_delivery_pos],
                                                         [pickup, delivery])
        pass

# class ThreeOpt(TourImprovementBehavior):
#     pass

# class LinKernighan(TourImprovementBehavior):
#     pass

# class Swap(TourImprovementBehavior):
#     pass
