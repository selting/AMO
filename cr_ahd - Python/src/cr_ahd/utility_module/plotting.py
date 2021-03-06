from typing import Union, List
import pandas as pd
import matplotlib.animation as ani
import matplotlib.pyplot as plt
from matplotlib.text import Annotation
import plotly.express as px
import plotly.graph_objects as go
from core_module import instance as it, solution as slt
from utility_module import utils as ut

config = dict({'scrollZoom': True})


def _make_depot_scatter(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier: int):
    carrier_ = solution.carriers[carrier]
    return go.Scatter(x=[instance.x_coords[carrier]],
                      y=[instance.y_coords[carrier]],
                      mode='markers+text',
                      marker=dict(
                          symbol='square',
                          size=15,
                          line=dict(color=ut.univie_colors_100[carrier], width=2),
                          color=ut.univie_colors_60[carrier]),
                      text=carrier,
                      name=f'Carrier {carrier} depot',
                      showlegend=False,
                      # legendgroup=carrier, hoverinfo='x+y'
                      )


def _make_tour_scatter(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier: int, tour: int):
    tour_ = solution.tours[tour]

    df = pd.DataFrame({
        'id_': tour_.routing_sequence[1:-1],
        'x': [instance.x_coords[v] for v in tour_.routing_sequence[1:-1]],
        'y': [instance.y_coords[v] for v in tour_.routing_sequence[1:-1]],
        'request': [instance.request_from_vertex(v) for v in tour_.routing_sequence[1:-1]],
        'type': [instance.vertex_type(v) for v in tour_.routing_sequence[1:-1]],
        'revenue': [instance.vertex_revenue[v] for v in tour_.routing_sequence[1:-1]],
        'tw_open': [instance.tw_open[v] for v in tour_.routing_sequence[1:-1]],
        'tw_close': [instance.tw_close[v] for v in tour_.routing_sequence[1:-1]],
    })
    df['type'] = df['type'].map({'pickup': '+', 'delivery': '-'})
    df['text'] = df['type'] + df['request'].astype(str)
    original_carrier_assignment = [instance.request_to_carrier_assignment[r] for r in
                                   [instance.request_from_vertex(v) for v in tour_.routing_sequence[1:-1]]]

    hover_text = []
    for v in tour_.routing_sequence[1:-1]:
        hover_text.append(
            f'Request {instance.request_from_vertex(v)}</br>{instance.vertex_type(v)}</br>'
            f'Vertex id: {v}</br>'
            f'Revenue: {instance.vertex_revenue[v]}</br>'
            f'TW: {ut.TimeWindow(instance.tw_open[v], instance.tw_close[v])}</br>'
            f'Tour\'s Travel Distance: {tour_.sum_travel_distance}')

    # colorscale = [(c, ut.univie_colors_100[c]) for c in range(instance.num_carriers)]
    return go.Scatter(
        x=df['x'],
        y=df['y'],
        mode='markers+text',
        marker=dict(
            symbol='circle',
            size=ut.linear_interpolation(df['revenue'].values, 15, 30, min(instance.vertex_revenue), max(instance.vertex_revenue)),
            line=dict(color=[ut.univie_colors_100[c] for c in original_carrier_assignment], width=2),
            color=ut.univie_colors_60[carrier]),
        text=df['text'],
        name=f'Carrier {carrier}, Tour {tour}',
        hovertext=hover_text
        # legendgroup=carrier, hoverinfo='x+y'
    )


def _make_unrouted_scatter(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier: int):
    carrier_ = solution.carriers[carrier]
    unrouted_vertices = ut.flatten([list(instance.pickup_delivery_pair(r)) for r in carrier_.unrouted_requests])

    df = pd.DataFrame({
        'id_': unrouted_vertices,
        'x': [instance.x_coords[v] for v in unrouted_vertices],
        'y': [instance.y_coords[v] for v in unrouted_vertices],
        'request': [instance.request_from_vertex(v) for v in unrouted_vertices],
        'type': [instance.vertex_type(v) for v in unrouted_vertices],
        'revenue': [instance.vertex_revenue[v] for v in unrouted_vertices],
        'tw_open': [instance.tw_open[v] for v in unrouted_vertices],
        'tw_close': [instance.tw_close[v] for v in unrouted_vertices],
        'original_carrier_assignment': [instance.request_to_carrier_assignment[r] for r in
                                        [instance.request_from_vertex(v) for v in unrouted_vertices]]})
    df['type'] = df['type'].map({'pickup': '+', 'delivery': '-'})
    df['text'] = df['type'] + df['request'].astype(str)

    hover_text = []
    for v in unrouted_vertices:
        hover_text.append(
            f'Request {instance.request_from_vertex(v)}</br>{instance.vertex_type(v)}</br>'
            f'Vertex id: {v}</br>'
            f'Revenue: {instance.vertex_revenue[v]}</br>'
            f'TW: [{instance.tw_open[v]} - {instance.tw_close[v]}]</br>'
        )

    return go.Scatter(
        x=df['x'], y=df['y'], mode='markers+text',
        marker=dict(
            symbol=['circle'] * len(unrouted_vertices),
            size=ut.linear_interpolation(df['revenue'].values, 15, 30, min(instance.vertex_revenue), max(instance.vertex_revenue)),
            line=dict(color=[ut.univie_colors_100[c] for c in df['original_carrier_assignment']], width=2),
            color=ut.univie_colors_60[carrier]),
        text=df['text'],
        textfont=dict(color='red'),
        name=f'Carrier {carrier}, unrouted',
        hovertext=hover_text
        # legendgroup=carrier, hoverinfo='x+y'
    )


def _make_unassigned_scatter(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution):
    vertex_id = ut.flatten(
        [[p, d] for p, d in [instance.pickup_delivery_pair(r) for r in solution.unassigned_requests]])
    df = pd.DataFrame({
        'id_': vertex_id,
        'x': [instance.x_coords[v] for v in vertex_id],
        'y': [instance.y_coords[v] for v in vertex_id],
        'request': [instance.request_from_vertex(v) for v in vertex_id],
        'type': [instance.vertex_type(v) for v in vertex_id],
        'revenue': [instance.vertex_revenue[v] for v in vertex_id],
        'original_carrier_assignment': [instance.request_to_carrier_assignment[r] for r in
                                        [instance.request_from_vertex(v) for v in vertex_id]]
    })
    df['type'] = df['type'].map({'pickup': '+', 'delivery': '-'})
    df['text'] = df['type'] + df['request'].astype(str)

    hover_text = []
    for v in vertex_id:
        hover_text.append(
            f'Request {instance.request_from_vertex(v)}</br>{instance.vertex_type(v)}</br>'
            f'Vertex id: {v}</br>'
            f'Revenue: {instance.vertex_revenue[v]}</br>'
            f'TW: [{instance.tw_open[v]} - {instance.tw_close[v]}]</br>'
        )

    return go.Scatter(
        x=df['x'], y=df['y'], mode='markers+text',
        marker=dict(
            symbol=['circle'] * len(df),
            size=ut.linear_interpolation(df['revenue'].values, 15, 30, min(instance.vertex_revenue), max(instance.vertex_revenue)),
            line=dict(color=[ut.univie_colors_100[c] for c in df['original_carrier_assignment']],
                      width=2),
            color='white'),
        text=df['text'],
        name=f'Unassigned',
        hovertext=hover_text
    )


def _make_tour_edges(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, carrier: int, tour: int):
    tour_ = solution.tours[tour]
    # creating arrows as annotations
    directed_edges = []
    for i in range(len(tour_.routing_sequence) - 1):
        from_vertex = tour_.routing_sequence[i]
        to_vertex = tour_.routing_sequence[i + 1]
        arrow_tail = (instance.x_coords[from_vertex], instance.y_coords[from_vertex])
        arrow_head = (instance.x_coords[to_vertex], instance.y_coords[to_vertex])
        min_rev = min(instance.vertex_revenue)
        max_rev = max(instance.vertex_revenue)

        anno = go.layout.Annotation(
            x=arrow_head[0], y=arrow_head[1], ax=arrow_tail[0], ay=arrow_tail[1],
            xref='x', yref='y', axref='x', ayref='y',
            text="",
            showarrow=True, arrowhead=2, arrowsize=2, arrowwidth=1,
            arrowcolor=ut.univie_colors_100[carrier],
            standoff=ut.linear_interpolation([instance.vertex_revenue[to_vertex]], 15, 30, min_rev, max_rev)[0] / 2,
            startstandoff=ut.linear_interpolation([instance.vertex_revenue[from_vertex]], 15, 30, min_rev, max_rev)[0] / 2,
            name=f'Carrier {carrier}, Tour {tour_}')
        directed_edges.append(anno)
    return directed_edges


def _add_carrier_solution(fig: go.Figure, instance, solution: slt.CAHDSolution, carrier_id: int):
    carrier = solution.carriers[carrier_id]
    scatter_traces = []
    edge_traces = []

    depot_scatter = _make_depot_scatter(instance, solution, carrier_id)
    fig.add_trace(depot_scatter)
    scatter_traces.append(depot_scatter)

    for tour_id in [tour.id_ for tour in carrier.tours] :
        tour_scatter = _make_tour_scatter(instance, solution, carrier_id, tour_id)
        fig.add_trace(tour_scatter)
        scatter_traces.append(tour_scatter)

        edges = _make_tour_edges(instance, solution, carrier_id, tour_id)
        for edge in edges:
            fig.add_annotation(edge)
        edge_traces.append(edges)

    if carrier.unrouted_requests:
        unrouted_scatter = _make_unrouted_scatter(instance, solution, carrier_id)
        fig.add_trace(unrouted_scatter)
        scatter_traces.append(unrouted_scatter)

    return scatter_traces, edge_traces


def plot_solution_2(instance: it.MDPDPTWInstance, solution: slt.CAHDSolution, title='', tours: bool = True,
                    time_windows: bool = True, arrival_times: bool = True, service_times: bool = True,
                    show: bool = False):
    fig = go.Figure()
    # [[scatter tour 0, scatter tour 1], [scatter tour 0, scatter tour 1, scatter tour 2], ...]
    scatters = []
    # [carrier 0:
    #   tour 0: [[edge_0, edge_1, edge_2, ...],
    #   tour 1: [edge_0, edge_1, edge_2, ...], ],
    # carrier 1:
    #   tour 0: [[edge_0, edge_1, edge_2, ...],
    #   tour 1: [edge_0, edge_1, edge_2, ...], ]
    # ]
    edges = []

    for c in range(len(solution.carriers)):
        scatter_traces, edge_traces = _add_carrier_solution(fig, instance, solution, c)
        scatters.append(scatter_traces)
        edges.append(edge_traces)

    if solution.unassigned_requests:
        unassigned_scatter = _make_unassigned_scatter(instance, solution)
        fig.add_trace(unassigned_scatter)
        scatters.append(unassigned_scatter)

    # custom buttons to hide edges
    button_dicts = []
    for c in range(len(solution.carriers)):
        ahd_solution = solution.carriers[c]
        for t in range(len(ahd_solution.tours)):
            button_dicts.append(
                dict(label=f'Carrier {c}, Tour {t}',
                     method='update',
                     args=[dict(visible=[True]),
                           dict(annotations=edges[c][t])
                           ],
                     # toggle on/off buttons -> not working as intended
                     # args2=[dict(visible=[True]),
                     #        dict(annotations=edges)
                     #        ],
                     )
            )
    button_dicts.append(
        dict(label=f'All',
             method='update',
             args=[dict(visible=[True]),
                   dict(annotations=ut.flatten(edges))
                   ],

             )
    )

    fig.update_layout(updatemenus=
                      [dict(type='buttons',
                            y=c / len(solution.carriers),
                            yanchor='auto',
                            active=-1,
                            buttons=button_dicts
                            )
                       ],
                      title=title,
                      # height=1200,
                      # width=1600
                      )
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1
    )

    if show:
        fig.show(config=config)


