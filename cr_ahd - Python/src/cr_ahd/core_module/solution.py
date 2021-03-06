import datetime as dt
import json
from typing import List, Sequence, Dict

import numpy as np

from core_module import instance as it, tour as tr
from utility_module import utils as ut


class CAHDSolution:
    # default, empty solution
    def __init__(self, instance: it.MDPDPTWInstance):
        self.id_: str = instance.id_
        self.meta: Dict[str, int] = instance.meta

        # requests that are not assigned to any carrier
        self.unassigned_requests: List[int] = list(instance.requests)

        # the current REQUEST-to-carrier (not vertex-to-carrier) allocation, initialized with nan for all requests
        self.request_to_carrier_assignment: List[int] = [None for _ in range(instance.num_requests)]

        self.tours: List[tr.Tour] = []
        self.carriers: List[AHDSolution] = [AHDSolution(c) for c in range(instance.num_carriers)]

        # solver configuration and other meta data
        self.solver_config = {config: None for config in ut.solver_config}
        self.timings = dict()
        # TODO find a better way to add available ls neighborhoods automatically
        self.local_search_move_counter = dict(PDPMove=0,
                                              PDPTwoOpt=0,
                                              PDPRelocate=0,
                                              PDPRelocate2=0,
                                              PDPLargeInterTourNeighborhood=0)

    def __str__(self):
        s = f'Solution {self.id_}\nObjective={round(self.objective(), 2)}'
        s += '\n'
        for c in self.carriers:
            s += str(c)
            s += '\n'
        return s

    def __repr__(self):
        return f'CAHDSolution for {self.id_}'

    def update_solver_config(self, solver):
        """
        The solver config describes the solution methods and used to solve an instance. For post-processing and
        comparing solutions it is thus useful to store the methods' names with the solution.
        """

        config: Dict[str, str] = self.solver_config
        int_auction = solver.intermediate_auction
        fin_auction = solver.final_auction
        if int_auction or fin_auction:
            config['solution_algorithm'] = 'CollaborativePlanning'
        else:
            config['solution_algorithm'] = 'IsolatedPlanning'

        config['tour_construction'] = solver.tour_construction.name
        config['tour_improvement'] = solver.tour_improvement.name
        config['tour_improvement_time_limit_per_carrier'] = solver.tour_improvement.time_limit_per_carrier
        config['neighborhoods'] = '+'.join([nbh.name for nbh in solver.tour_improvement.neighborhoods])
        config['time_window_offering'] = solver.time_window_offering.name
        config['time_window_selection'] = solver.time_window_selection.name
        config['num_int_auctions'] = solver.num_intermediate_auctions

        if int_auction:
            config['int_auction_tour_construction'] = int_auction.tour_construction.name
            config['int_auction_tour_improvement'] = int_auction.tour_improvement.name
            config['int_auction_neighborhoods'] = '+'.join([nbh.name for nbh in int_auction.tour_improvement.neighborhoods])
            config['int_auction_num_submitted_requests'] = int_auction.request_selection.num_submitted_requests
            config['int_auction_request_selection'] = int_auction.request_selection.name
            config['int_auction_bundle_generation'] = int_auction.bundle_generation.name
            try:
                # for bundle generation with LimitedBundlePoolGenerationBehavior
                config['int_auction_bundling_valuation'] = int_auction.bundle_generation.bundling_valuation.name
            except KeyError:
                None
            config['int_auction_num_auction_bundles'] = int_auction.bundle_generation.num_auction_bundles
            config['int_auction_bidding'] = int_auction.bidding.name
            config['int_auction_winner_determination'] = int_auction.winner_determination.name
            config['int_auction_num_auction_rounds'] = int_auction.num_auction_rounds

        if fin_auction:
            config['fin_auction_tour_construction'] = fin_auction.tour_construction.name
            config['fin_auction_tour_improvement'] = fin_auction.tour_improvement.name
            config['fin_auction_neighborhoods'] = '+'.join([nbh.name for nbh in fin_auction.tour_improvement.neighborhoods])
            config['fin_auction_num_submitted_requests'] = fin_auction.request_selection.num_submitted_requests
            config['fin_auction_request_selection'] = fin_auction.request_selection.name
            config['fin_auction_bundle_generation'] = fin_auction.bundle_generation.name
            try:
                # for bundle generation with LimitedBundlePoolGenerationBehavior
                config['fin_auction_bundling_valuation'] = fin_auction.bundle_generation.bundling_valuation.name
            except KeyError:
                None
            config['fin_auction_num_auction_bundles'] = fin_auction.bundle_generation.num_auction_bundles
            config['fin_auction_bidding'] = fin_auction.bidding.name
            config['fin_auction_winner_determination'] = fin_auction.winner_determination.name
            config['fin_auction_num_auction_rounds'] = fin_auction.num_auction_rounds

        pass

    def sum_travel_distance(self):
        return sum(c.sum_travel_distance() for c in self.carriers)

    def sum_travel_duration(self):
        return sum((c.sum_travel_duration() for c in self.carriers), dt.timedelta(0))

    def sum_load(self):
        return sum(c.sum_load() for c in self.carriers)

    def sum_revenue(self):
        return sum(c.sum_revenue() for c in self.carriers)

    def objective(self):
        return sum(c.objective() for c in self.carriers)

    def sum_profit(self):
        return sum(c.sum_profit() for c in self.carriers)

    def num_carriers(self):
        return len(self.carriers)

    def num_tours(self):
        return len(self.tours)

    def num_routing_stops(self):
        return sum(c.num_routing_stops() for c in self.carriers)

    def avg_acceptance_rate(self):
        # average over all carriers
        return sum([c.acceptance_rate for c in self.carriers]) / self.num_carriers()

    def assign_requests_to_carriers(self, requests: Sequence[int], carriers: Sequence[int]):
        for r, c in zip(requests, carriers):
            self.request_to_carrier_assignment[r] = c
            self.unassigned_requests.remove(r)
            self.carriers[c].assigned_requests.append(r)
            self.carriers[c].unrouted_requests.append(r)

    def free_requests_from_carriers(self, instance: it.MDPDPTWInstance, requests: Sequence[int]):
        """
        removes the given requests from their route and sets them to be unassigned and not accepted (not_accepted !=
        rejected)

        :param instance:
        :param requests:
        :return:
        """

        for request in requests:
            carrier: AHDSolution = self.carriers[self.request_to_carrier_assignment[request]]
            tour = self.tour_of_request(request)
            tour.pop_and_update(instance, [tour.vertex_pos[v] for v in instance.pickup_delivery_pair(request)])
            tour.requests.remove(request)

            # retract the request from the carrier
            carrier.assigned_requests.remove(request)
            carrier.accepted_requests.remove(request)
            carrier.routed_requests.remove(request)
            self.request_to_carrier_assignment[request] = np.nan
            self.unassigned_requests.append(request)

    def clear_carrier_routes(self, carrier_ids):
        """
        delete all existing routes of the given carrier and move all accepted requests to the list of unrouted requests
        :param carrier_ids:
        """
        if carrier_ids is None:
            carrier_ids = [carrier.id_ for carrier in self.carriers]

        for carrier_id in carrier_ids:
            carrier = self.carriers[carrier_id]
            carrier.unrouted_requests = carrier.accepted_requests[:]
            carrier.routed_requests.clear()
            for tour_id in [tour.id_ for tour in carrier.tours]:
                self.tours[tour_id] = None
            carrier.tours.clear()

    def get_free_tour_id(self):
        if None in self.tours:
            tour_id = self.tours.index(None)
        else:
            tour_id = len(self.tours)
        return tour_id

    def as_dict(self):
        """The solution as a nested python dictionary"""
        return {carrier.id_: carrier.as_dict() for carrier in self.carriers}

    def summary(self):
        summary = {
            'id_': self.id_,
            'num_carriers': self.num_carriers(),
            'objective': self.objective(),
            'sum_profit': self.sum_profit(),
            'sum_travel_distance': self.sum_travel_distance(),
            'sum_travel_duration': self.sum_travel_duration(),
            # 'sum_wait_duration': self.sum_wait_duration(),
            'sum_load': self.sum_load(),
            'sum_revenue': self.sum_revenue(),
            'num_tours': self.num_tours(),
            'num_routing_stops': self.num_routing_stops(),
            'acceptance_rate': self.avg_acceptance_rate(),
            **self.timings,
            'carrier_summaries': {c.id_: c.summary() for c in self.carriers}
        }
        summary.update(self.solver_config)
        return summary

    def write_to_json(self):
        path = ut.output_dir.joinpath(f'{self.num_carriers()}carriers',
                                         self.id_ + '_' + self.solver_config['solution_algorithm'])
        path = ut.unique_path(path.parent, path.stem + '_#{:03d}' + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, mode='w') as f:
            json.dump({'summary': self.summary(), 'solution': self.as_dict()}, f, indent=4, cls=ut.MyJSONEncoder)
        pass

    def tour_of_request(self, request: int) -> tr.Tour:
        for tour in self.tours:
            if request in tour.requests:
                return tour
        return None


class AHDSolution:
    def __init__(self, carrier_index):
        self.id_ = carrier_index
        # self.depots = [carrier_index]  # maybe it's better to store the depots in this class rather than in CAHD?!
        self.assigned_requests: List = []
        self.accepted_requests: List = []
        self.rejected_requests: List = []
        self.unrouted_requests: List = []
        self.routed_requests: List = []
        self.acceptance_rate: float = 0
        self.tours: List[tr.Tour] = []

    def __str__(self):
        s = f'---// Carrier ID: {self.id_} //---' \
            f'\tObjective={round(self.objective(), 4)}, ' \
            f'Acceptance Rate={round(self.acceptance_rate, 2)}, ' \
            f'Assigned={self.assigned_requests}, ' \
            f'Accepted={self.accepted_requests}, ' \
            f'Unrouted={self.unrouted_requests}, ' \
            f'Routed={self.routed_requests}'
        s += '\n'
        for tour in self.tours:
            s += str(tour)
            s += '\n'
        return s

    def __repr__(self):
        return f'Carrier (AHDSolution) {self.id_}'

    def num_routing_stops(self):
        return sum(t.num_routing_stops for t in self.tours)

    def sum_travel_distance(self):
        return sum(t.sum_travel_distance for t in self.tours)

    def sum_travel_duration(self):
        return sum((t.sum_travel_duration for t in self.tours), dt.timedelta(0))

    def sum_load(self):
        return sum(t.sum_load for t in self.tours)

    def sum_revenue(self):
        return sum(t.sum_revenue for t in self.tours)

    def sum_profit(self):
        return sum(t.sum_profit for t in self.tours)

    def objective(self):
        return self.sum_profit()

    def as_dict(self):
        return {
            # 'id_': self.id_,
            'tours': {
                tour.id_: tour.as_dict() for tour in self.tours
            },
        }

    def summary(self) -> dict:
        return {
            # 'id_': self.id_,
            'num_tours': len(self.tours),
            'num_routing_stops': self.num_routing_stops(),
            'sum_profit': self.objective(),
            'sum_travel_distance': self.sum_travel_distance(),
            'sum_travel_duration': self.sum_travel_duration(),
            # 'sum_wait_duration': self.sum_wait_duration(),
            'sum_load': self.sum_load(),
            'sum_revenue': self.sum_revenue(),
            'acceptance_rate': self.acceptance_rate,
            'tour_summaries': {t.id_: t.summary() for t in self.tours}
        }
