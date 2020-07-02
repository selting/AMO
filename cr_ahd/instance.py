import vertex as vx
import vehicle as vh
import carrier as cr
from utils import split_iterable, make_dist_matrix, opts

from copy import copy

import pandas as pd
import matplotlib.pyplot as plt


class Instance(object):
    """Class to store CR_AHD instances
    """

    def __init__(self, id_, requests, carriers):
        self.id_ = id_
        self.requests = requests
        self.carriers = carriers
        self.dist_matrix = make_dist_matrix([*self.requests, *[c.depot for c in self.carriers]])
        pass

    def __str__(self):
        return f'Instance {self.id_} with {len(self.requests)} customers and {len(self.carriers)} carriers'

    def cheapest_insertion_construction(self, verbose=opts['verbose']):
        if verbose > 0:
            print('Cheapest Insertion Construction:')
        for c in self.carriers:
            c._cheapest_insertion_construction(self.dist_matrix)
            if verbose > 0:
                print(f'Route cost of carrier {c.id_}: {c.route_cost()}')
        pass

    def I1_construction(self, verbose=opts['verbose']):
        if verbose > 0:
            print(f'I1 route construction for {self}')
        for c in self.carriers:
            c._I1_construction(dist_matrix=self.dist_matrix)
            if verbose > 0:
                print(f'Route cost of carrier {c.id_}: {c.route_cost()}')
        pass

    def total_cost(self):
        total_cost = 0
        for c in self.carriers:
            for v in c.vehicles:
                total_cost += v.tour.cost
        return total_cost

    def plot(self, ax: plt.Axes = plt.gca(), annotate: bool = True, alpha: float = 1):
        # plot depots
        depots = [c.depot for c in self.carriers]
        for d in depots:
            ax.scatter(d.coords.x, d.coords.y, marker='s', alpha=alpha)
            if annotate:
                ax.annotate(f'{d.id_}', xy=d.coords)

        # plot requests locations
        for r in self.requests:
            ax.scatter(r.coords.x, r.coords.y, alpha=alpha, color='grey')
            if annotate:
                ax.annotate(f'{r.id_}', xy=r.coords)

        return ax


def read_solomon(name: str, num_carriers: int = 3) -> Instance:
    # TODO: a more efficient way of reading the data, e.g. by reading all vertices at once and split off the depot after; and by not using pd to read vehicles
    vehicles = pd.read_csv(f'../data/Solomon/{name}.txt', skiprows=4, nrows=1, delim_whitespace=True,
                           names=['number', 'capacity'])
    vehicles = [vh.Vehicle('v' + str(i), vehicles.capacity[0]) for i in range(vehicles.number[0])]
    vehicles = split_iterable(vehicles, num_carriers)

    cols = ['cust_no', 'x_coord', 'y_coord', 'demand', 'ready_time', 'due_date', 'service_duration']
    requests = pd.read_csv(f'../data/Solomon/{name}.txt', skiprows=10, delim_whitespace=True, names=cols)
    requests = [vx.Vertex('r' + str(row.cust_no - 1), row.x_coord, row.y_coord, row.ready_time, row.due_date) for row in
                requests.itertuples()]

    depot = pd.read_csv(f'../data/Solomon/{name}.txt', skiprows=9, nrows=1, delim_whitespace=True,
                        names=cols)  # TODO: how to handle depots? read in read_solomon?
    depot = vx.Vertex('d1', depot.x_coord[0], depot.y_coord[0], depot.ready_time[0], depot.due_date[0])

    carriers = []
    for i in range(num_carriers):
        c = cr.Carrier('c' + str(i), copy(depot), next(vehicles))
        c.depot.id_ = 'd' + str(i)
        carriers.append(c)

    inst = Instance(name, requests, carriers)

    if opts['verbose'] > 0:
        print(f'Successfully read Solomon {name} with {num_carriers} carriers.')
        print(inst)

    return inst
