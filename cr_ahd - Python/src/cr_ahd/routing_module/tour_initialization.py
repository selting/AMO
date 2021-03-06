import random
from abc import ABC, abstractmethod
from typing import List

from core_module import instance as it, solution as slt, tour as tr
from utility_module import utils as ut


# =====================================================================================================================
# single-criterion-based
# =====================================================================================================================

class TourInitializationBehavior(ABC):
    """
    Visitor Interface to apply a tour initialization heuristic to either an instance (i.e. each of its carriers)
    or a single specific carrier.
    """

    def execute(self, instance: it.MDPDPTWInstance, solution: slt.CAHDSolution):
        for carrier in range(len(solution.carriers)):
            self._initialize_carrier(instance, solution, carrier)
        pass

    def _initialize_carrier(self, instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier_id: int):
        carrier = solution.carriers[carrier_id]
        assert carrier.unrouted_requests

        # create (potentially multiple) initial pendulum tour(s)
        num_pendulum_tours = instance.carriers_max_num_tours
        for pendulum_tour in range(num_pendulum_tours):

            best_request = None
            best_evaluation = -float('inf')

            for request in carrier.unrouted_requests:

                evaluation = self._request_evaluation(instance, solution, request)

                # update the best known seed
                if evaluation > best_evaluation:
                    best_request = request
                    best_evaluation = evaluation

            # create the pendulum tour
            carrier = solution.carriers[carrier_id]
            if len(carrier.tours) >= instance.carriers_max_num_tours:
                raise ut.ConstraintViolationError(
                    f'Cannot create new route with request {best_request} for carrier {carrier.id_}.'
                    f' Max. number of vehicles is {instance.carriers_max_num_tours}!'
                    f' ({instance.id_})')
            tour_id = solution.get_free_tour_id()
            assert tour_id < instance.num_carriers * instance.carriers_max_num_tours
            tour = tr.Tour(tour_id, depot_index=carrier.id_)

            if tour.insertion_feasibility_check(instance, [1, 2], instance.pickup_delivery_pair(best_request)):
                tour.insert_and_update(instance, [1, 2], instance.pickup_delivery_pair(best_request))
                tour.requests.add(best_request)

            else:
                raise ut.ConstraintViolationError(
                    f'Cannot create new route with request {best_request} for carrier {carrier.id_}.')

            if tour_id < len(solution.tours):
                solution.tours[tour_id] = tour
            else:
                solution.tours.append(tour)
            carrier.tours.append(tour)
            carrier.unrouted_requests.remove(best_request)
            carrier.routed_requests.append(best_request)


    @abstractmethod
    def _request_evaluation(self, instance: it.MDPDPTWInstance, solution:slt.CAHDSolution, request: int):
        """
        See below

        :param instance:
        :param solution:
        :param request:
        :return:
        """
        pass


class EarliestDueDateTourInitialization(TourInitializationBehavior):
    def _request_evaluation(self, instance, solution, request):
        return - kwargs['tw_close'][delivery_idx].total_seconds


class FurthestDistanceTourInitialization(TourInitializationBehavior):
    def _request_evaluation(self, instance, solution, request):
        x_midpoint, y_midpoint = ut.midpoint_(kwargs['x_coords'][pickup_idx], kwargs['x_coords'][delivery_idx],
                                              kwargs['y_coords'][pickup_idx], kwargs['y_coords'][delivery_idx])
        return ut.euclidean_distance(kwargs['x_depot'], kwargs['y_depot'], x_midpoint, y_midpoint)


class ClosestDistanceTourInitialization(TourInitializationBehavior):
    def _request_evaluation(self, instance, solution, request):
        x_midpoint, y_midpoint = ut.midpoint_(kwargs['x_coords'][pickup_idx], kwargs['x_coords'][delivery_idx],
                                              kwargs['y_coords'][pickup_idx], kwargs['y_coords'][delivery_idx])
        return - ut.euclidean_distance(kwargs['x_depot'], kwargs['y_depot'], x_midpoint, y_midpoint)


# =====================================================================================================================
# Graph-based
# =====================================================================================================================

class MaxCliqueTourInitialization(ABC):
    """
    based on
    [1] Lu,Q., & Dessouky,M.M. (2006). A new insertion-based construction heuristic for solving the pickup and
    delivery problem with time windows. European Journal of Operational Research, 175(2), 672???687.
    https://doi.org/10.1016/j.ejor.2005.05.012
    """

    def execute(self, instance: it.MDPDPTWInstance, solution: slt.CAHDSolution):
        for carrier in range(len(solution.carriers)):
            self._initialize_carrier(instance, solution, carrier)
        pass

    def _initialize_carrier(self, instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier: int):
        carrier_ = solution.carriers[carrier]
        assert len(solution.carrier_depots[carrier]) == 1, f'graph based initialization only available for single-depot'
        assert carrier_.unrouted_requests

        # find candidates for initial pendulum tours

        # create the graph G_N
        g_nodes = list(range(len(carrier_.unrouted_requests)))  # each request is a node
        g_arcs = self.g_arcs(instance, solution, carrier)

        seed_idx = self.max_clique(g_nodes, g_arcs)  # returns indices corresponding to the list of unrouted!

        if seed_idx is not None:
            assert len(seed_idx) <= instance.carriers_max_num_tours

            # create the pendulum tours, popping the seeds off the list of unrouted requires reverse traversal
            for i in sorted(seed_idx, reverse=True):
                seed = carrier_.unrouted_requests[i]
                tour_id = solution.num_tours()
                tour = tr.Tour(tour_id, solution.carrier_depots[carrier][0])
                tour.insert_and_update(instance, [1, 2], instance.pickup_delivery_pair(seed))
                tour.requests.add(seed)
                # solution.request_to_tour_assignment[seed] = carrier_.num_tours()
                carrier_.tours.append(tour)
                carrier_.unrouted_requests.pop(i)
                carrier_.routed_requests.append(seed)

        pass

    def g_arcs(self, instance, solution, carrier):
        carrier_ = solution.carriers[carrier]
        num_requests = len(carrier_.unrouted_requests)

        g_arcs = [[0] * num_requests for _ in range(num_requests)]  # n*n matrix of zeros
        # g_arcs = np.zeros((instance.num_carriers, instance.num_carriers))  # twice as fast

        # create arcs for request pairs if and only if NO vehicle can serve i_request and j_request in a single tour
        for i, i_request in enumerate(carrier_.unrouted_requests[:-1]):
            i_pickup, i_delivery = instance.pickup_delivery_pair(i_request)

            for j, j_request in enumerate(carrier_.unrouted_requests[i+1:], start=1):
                j_pickup, j_delivery = instance.pickup_delivery_pair(j_request)

                tour_ = tr.Tour('tmp', solution.carrier_depots[carrier][0])

                # make sure that the first request is feasible alone
                if not tour_.insertion_feasibility_check(instance, [1, 2], [i_pickup, i_delivery]):
                    raise ut.ConstraintViolationError(
                        message=f'[{instance.id_}] Request {i_request} cannot feasibly be served by carrier {carrier}!')
                tour_.insert_and_update(instance, [1, 2], [i_pickup, i_delivery])
                tour_.requests.add(i_request)
                # solution.request_to_tour_assignment[i_request] = tour_.id_

                # try all insertion positions to see whether all are infeasible
                feasible = False
                for j_pickup_pos in range(1, 4):
                    for j_delivery_pos in range(j_pickup_pos + 1, 5):

                        # connect the nodes if insertion is infeasible
                        if tour_.insertion_feasibility_check(instance, [j_pickup_pos, j_delivery_pos],
                                                             [j_pickup, j_delivery]):
                            feasible = True
                            break

                    if feasible:
                        break

                # only if no feasible insertion for j_request was found, an arc is created
                if not feasible:
                    g_arcs[i][j] = 1
                    g_arcs[j][i] = 1  # create both triangles of the matrix

        return g_arcs

    def _request_evaluation(self, pickup_idx: int, delivery_idx: int, **kwargs):
        pass

    def max_clique(self, g_nodes: List[int], g_arcs: List[List[int]]):
        """
        will modify g_nodes and g_arcs in place!
        :param g_nodes:
        :param g_arcs:
        :return:
        """

        def trim_non_neighbors(nodes, arcs, i, marked):
            """remove nodes that have no edge linking to i from the graph. also drop all these non-neighbors' arcs.
             Note: Modifies the nodes and arcs in place!"""
            for j in nodes.copy():
                if i == j:
                    continue
                if arcs[i][j] == 0:
                    # remove arcs of j_node
                    for k in nodes:
                        arcs[k][j] = 0
                        arcs[j][k] = 0
                    # remove j from graph nodes
                    nodes.remove(j)
                    # mark j
                    marked[j] = True
            pass

        max_clique = None
        max_clique_degree = 0

        # [1] select each node as the initial node once
        for i in g_nodes:
            g_nodes_copy = g_nodes.copy()
            g_arcs_copy = [x.copy() for x in g_arcs]
            marked = [False] * len(g_nodes_copy)
            marked[i] = True
            trim_non_neighbors(g_nodes_copy, g_arcs_copy, i, marked)

            unmarked_max_degree = 0
            while not all(marked):
                # [2] select & mark an arbitrary node with max number of incident edges
                unmarked_max_degree = max([sum(w) for v, w in enumerate(g_arcs_copy) if marked[v] is False])
                # stop if current clique has lower degree than the max_clique
                if unmarked_max_degree <= max_clique_degree:
                    break
                unmarked_max_degree_nodes = [node for node in g_nodes_copy if
                                             sum(g_arcs_copy[node]) == unmarked_max_degree and marked[node] is False]

                r = random.choice(unmarked_max_degree_nodes)  # TODO why do this randomly?! no need
                marked[r] = True

                # [3] remove nodes that have no edge linking to r
                trim_non_neighbors(g_nodes_copy, g_arcs_copy, r, marked)

            # replace the current clique if it has a higher degree than the best known max clique
            if unmarked_max_degree > max_clique_degree:
                max_clique_degree = unmarked_max_degree
                max_clique = g_nodes_copy

        return max_clique


if __name__ == '__main__':
    MaxCliqueTourInitialization().max_clique(
        list(range(6)),
        [
            [0, 1, 1, 1, 0, 1],
            [1, 0, 1, 1, 0, 0],
            [1, 1, 0, 1, 1, 0],
            [1, 1, 1, 0, 0, 0],
            [0, 0, 1, 0, 0, 1],
            [1, 0, 0, 0, 1, 0]
        ]
    )
