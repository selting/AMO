import datetime as dt

import src.cr_ahd.utility_module.utils as ut
from abc import ABC, abstractmethod


class BaseVertex(ABC):
    def __init__(self, id_: str, x_coord: float, y_coord: float):
        self.id_ = id_
        self.coords = ut.Coordinates(x_coord, y_coord)

    @abstractmethod
    def to_dict(self):
        pass


class DepotVertex(BaseVertex):
    def __init__(self, id_: str,
                 x_coord: float,
                 y_coord: float,
                 carrier_assignment: str = None):
        super().__init__(id_, x_coord, y_coord)
        self.carrier_assignment = carrier_assignment
        self.tw = ut.TIME_HORIZON
        self.service_duration = dt.timedelta(0)
        self.demand = 0
        self.assigned = False

    def __str__(self):
        return f'{self.__dict__}'

    def to_dict(self):
        return {
            'id_': self.id_,
            'x_coord': self.coords.x,
            'y_coord': self.coords.y,
            'carrier_assignment': self.carrier_assignment,
        }


class Vertex(BaseVertex):

    def __init__(self,
                 id_: str,
                 x_coord: float,
                 y_coord: float,
                 tw_open: dt.datetime,
                 tw_close: dt.datetime,
                 **kwargs
                 ):
        super().__init__(id_, x_coord, y_coord)
        self._tw = ut.TimeWindow(tw_open, tw_close)  # time windows opening and closing
        # self._assigned = False
        # self._routed = False

    def __str__(self):
        return f'Vertex (ID={self.id_}, {self.coords}, {self.tw}, assigned={self.assigned}, routed={self.routed})'

    def to_dict(self):
        return {
            'id_': self.id_,
            'x_coord': self.coords.x,
            'y_coord': self.coords.y,
            'tw_open': self.tw.e,
            'tw_close': self.tw.l,
        }

    @property
    def tw(self):
        return self._tw

    @tw.setter
    def tw(self, new_tw):
        assert self.tw == ut.TIME_HORIZON, f'Cannot override an already agreed-upon time window'
        self._tw = new_tw

    # @property
    # def routed(self):
    #     return self._routed
    #
    # @routed.setter
    # def routed(self, routed: bool):
    #     # XOR: can only set from True to False or vice versa
    #     assert bool(routed) ^ bool(
    #         self.routed), f'routed attribute of {self} can only set from True to False or vice versa'
    #     self._routed = routed


def midpoint(vertex_A: BaseVertex, vertex_B: BaseVertex):
    return ut.Coordinates((vertex_A.coords.x + vertex_B.coords.x) / 2, (vertex_A.coords.y + vertex_B.coords.y) / 2)
