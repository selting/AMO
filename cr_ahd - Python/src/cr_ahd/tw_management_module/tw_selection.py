import abc
import datetime as dt
import logging
import random
from typing import List

from src.cr_ahd.utility_module.utils import TimeWindow, END_TIME

logger = logging.getLogger(__name__)


class TWSelectionBehavior(abc.ABC):
    # TODO maybe in the future, i have to store also time window preferences / tw selection behavior in the instance
    def execute(self, tw_offer_set: List[TimeWindow], request: int):
        # may yield False if no TW fits the preference
        if tw_offer_set:
            selected_tw = self.select_tw(tw_offer_set, request)

        # if no TW could be offered
        else:
            selected_tw = False
        return selected_tw

    @abc.abstractmethod
    def select_tw(self, tw_offer_set, request: int):
        pass


class UniformPreference(TWSelectionBehavior):
    """Will randomly select a TW """

    def select_tw(self, tw_offer_set, request: int):
        return random.choice(tw_offer_set)


class UnequalPreference(TWSelectionBehavior):
    """
    Following Köhler,C., Ehmke,J.F., & Campbell,A.M. (2020). Flexible time window management for attended home
    deliveries. Omega, 91, 102023. https://doi.org/10.1016/j.omega.2019.01.001
    Late time windows exhibit a much higher popularity and are requested by 90% of the customers.
    """

    def select_tw(self, tw_offer_set, request: int):
        # preference can either be for early (10%) or late (90%) time windows
        pref = random.random()

        # early preference
        if pref <= 0.1:
            attractive_tws = [tw for tw in tw_offer_set if
                              tw.close <= dt.datetime(1, 1, 1, 0) + (END_TIME - dt.datetime(1, 1, 1, 0)) / 2]
        # late preference
        else:
            attractive_tws = [tw for tw in tw_offer_set if
                              tw.open >= dt.datetime(1, 1, 1, 0) + (END_TIME - dt.datetime(1, 1, 1, 0)) / 2]
        if attractive_tws:
            return random.choice(attractive_tws)
        else:
            return False


class EarlyPreference(TWSelectionBehavior):
    """Will always select the earliest TW available based on the time window opening"""

    def select_tw(self, tw_offer_set, request: int):
        return min(tw_offer_set, key=lambda tw: tw.open)


class LatePreference(TWSelectionBehavior):
    """Will always select the latest TW available based on the time window closing"""

    def select_tw(self, tw_offer_set, request: int):
        return max(tw_offer_set, key=lambda tw: tw.close)

# class PreferEarlyAndLate(TWSelectionBehavior):
#     def select_tw(self, tw_offer_set):
#         pass