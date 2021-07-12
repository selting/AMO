import logging

from src.cr_ahd.core_module import instance as it, solution as slt
from src.cr_ahd.tw_management_module import tw_offering as two, tw_selection as tws
from src.cr_ahd.utility_module import utils as ut

logger = logging.getLogger(__name__)


class TWManagementNoTW:
    def execute(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, request: int):
        carrier_ = solution.carriers[carrier]
        carrier_.accepted_requests.append(request)
        carrier_.acceptance_rate = len(carrier_.accepted_requests) / len(carrier_.assigned_requests)
        return True


class TWManagementSingle:
    """
    handles a single request/customer at a time. a new routing is required after each call to this class'
    execute function! Requests must also be assigned one at a time
    """

    def execute(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, request: int):
        carrier_ = solution.carriers[carrier]
        offer_set = two.FeasibleTW().execute(instance, solution, carrier, request)  # which TWs to offer?
        # selected_tw = tws.UniformPreference().execute(offer_set, request)  # which TW is selected?
        selected_tw = tws.UnequalPreference().execute(offer_set, request)  # which TW is selected?

        if selected_tw:

            # set the TW open and close times
            pickup_vertex, delivery_vertex = instance.pickup_delivery_pair(request)
            solution.tw_open[delivery_vertex] = selected_tw.open
            solution.tw_close[delivery_vertex] = selected_tw.close
            carrier_.accepted_requests.append(request)
            carrier_.acceptance_rate = len(carrier_.accepted_requests) / len(carrier_.assigned_requests)
            return True

        # in case no feasible TW exists for a given request
        else:
            logger.error(f'[{instance.id_}] No feasible TW can be offered from Carrier {carrier} to request {request}')
            pickup_vertex, delivery_vertex = instance.pickup_delivery_pair(request)
            solution.tw_open[delivery_vertex] = ut.START_TIME
            solution.tw_close[delivery_vertex] = ut.START_TIME
            carrier_.rejected_requests.append(request)
            carrier_.unrouted_requests.pop(0)
            carrier_.acceptance_rate = len(carrier_.accepted_requests) / len(carrier_.assigned_requests)
            return False


class TWManagementSingleOriginalDepot:
    """
    ONLY FOR SINGLE CARRIER MULTI-DEPOT INSTANCES
    """

    def execute(self, instance: it.PDPInstance, solution: slt.CAHDSolution, carrier: int, request: int):
        assert instance.num_carriers == 1
        carrier_ = solution.carriers[carrier]
        offer_set = two.FeasibleTWOriginalDepot().execute(instance, solution, carrier, request)  # which TWs to offer?
        # selected_tw = tws.UniformPreference().execute(offer_set, request)  # which TW is selected?
        selected_tw = tws.UnequalPreference().execute(offer_set, request)  # which TW is selected?

        if selected_tw:

            # set the TW open and close times
            pickup_vertex, delivery_vertex = instance.pickup_delivery_pair(request)
            solution.tw_open[delivery_vertex] = selected_tw.open
            solution.tw_close[delivery_vertex] = selected_tw.close
            carrier_.accepted_requests.append(request)
            carrier_.acceptance_rate = len(carrier_.accepted_requests) / len(carrier_.assigned_requests)
            return True

        # in case no feasible TW exists for a given request
        else:
            logger.error(f'[{instance.id_}] No feasible TW can be offered from Carrier {carrier} to request {request}')
            pickup_vertex, delivery_vertex = instance.pickup_delivery_pair(request)
            solution.tw_open[delivery_vertex] = ut.START_TIME
            solution.tw_close[delivery_vertex] = ut.START_TIME
            carrier_.rejected_requests.append(request)
            carrier_.unrouted_requests.pop(0)
            carrier_.acceptance_rate = len(carrier_.accepted_requests) / len(carrier_.assigned_requests)
            return False