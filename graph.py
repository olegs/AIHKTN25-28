from collections import Counter
from collections import defaultdict
from itertools import combinations

import networkx as nx
from bokeh.models import GraphRenderer, ColumnDataSource, LabelSet, NodesAndLinkedEdges, MultiLine, \
    StaticLayoutProvider, Circle
from bokeh.plotting import figure, from_networkx
from sklearn.preprocessing import minmax_scale


def build_entities_graph(connections_by_pid, summarized_data):
    # Reverse mapping: paper → set of entities
    paper_to_entities = defaultdict(set)
    for entity in summarized_data:
        for pid in entity["cited_in"]:
            paper_to_entities[pid].add(entity["name"])

    # If we have less than 2 entities, we can't build a graph
    if len(set().union(*paper_to_entities.values())) < 2:
        # Return an empty graph
        return nx.Graph()

    entities_pair_weights = Counter()
    # Loop through each paper and count co-occurrences
    for entities_set in paper_to_entities.values():
        for g1, g2 in combinations(sorted(entities_set), 2):
            entities_pair_weights[(g1, g2)] += 1

    weighted_entities_pairs = defaultdict(float)
    for pid, entities_set in paper_to_entities.items():
        weight = connections_by_pid.get(pid, 1)  # fallback to 1
        for g1, g2 in combinations(sorted(entities_set), 2):
            weighted_entities_pairs[(g1, g2)] += weight

    # Build the graph from your weighted_entity_pairs
    g = nx.Graph()
    for (g1, g2), weight in weighted_entities_pairs.items():
        g.add_edge(g1, g2, weight=weight)

    return g


def plot_entities_graph(g):
    print(f"Plotting graph with {len(g.nodes)} nodes and {len(g.edges)} edges")

    # Check if the graph has any nodes or edges
    if len(g.nodes) == 0 or len(g.edges) == 0:
        # Create a simple figure with a message if the graph is empty
        p = create_plot()
        p.text(x=50, y=50,
               text=["No connections found in the data"],
               text_align="center", text_baseline="middle",
               text_font_size="20px")
        return p

    # Normalize weights to have reasonable line widths
    weights = [d['weight'] for (_, _, d) in (list(g.edges(data=True)))]
    line_widths = minmax_scale(weights) * 6 + 1

    # create Graph
    nodes = list(g.nodes)
    edges = list(g.edges)
    nodes_to_idx = {v: i for i, v in enumerate(nodes)}

    graph = GraphRenderer()
    # Graph API requires id to be integer
    ids = list(range(len(nodes_to_idx)))
    graph.node_renderer.data_source.data = dict(
        index=ids,
    )
    # Set node glyph
    graph.node_renderer.glyph = Circle(radius=15, fill_color="skyblue")
    graph.node_renderer.hover_glyph = Circle(radius=20, fill_color="orange")
    graph.node_renderer.selection_glyph = Circle(radius=20, fill_color="red")

    graph.edge_renderer.data_source.data = dict(
        start=[nodes_to_idx[u] for u, v in edges],
        end=[nodes_to_idx[v] for u, v in edges],
        line_widths=line_widths
    )
    # Set edge glyph
    graph.edge_renderer.glyph = MultiLine(line_color="gray", line_alpha=0.8, line_width="line_widths")
    graph.edge_renderer.selection_glyph = MultiLine(line_color="navy", line_width=3)
    graph.edge_renderer.hover_glyph = MultiLine(line_color="navy", line_width=3)

    # Set selection policy
    graph.selection_policy = NodesAndLinkedEdges()
    graph.inspection_policy = NodesAndLinkedEdges()

    # start of layout code
    pos = nx.spring_layout(g, k=13, iterations=300, seed=42)
    xs = [pos[v][0] for v in nodes]
    ys = [pos[v][1] for v in nodes]
    xs, ys = minmax_scale(xs) * 100, minmax_scale(ys) * 100
    graph_layout = dict(zip(nodes, zip(xs, ys)))
    graph.layout_provider = StaticLayoutProvider(graph_layout=graph_layout)

    # Add Node labels
    source = ColumnDataSource(dict(x=xs, y=ys, name=nodes))
    labels = LabelSet(x='x', y='y', text='name', source=source,
                      background_fill_color='white',
                      text_font_size='13px',
                      background_fill_alpha=.7,
                      y_offset=15)  # Offset labels to not cover nodes

    # Plot em
    p = create_plot()

    # Add renderers to the figure
    p.renderers.append(graph)
    p.renderers.append(labels)

    return p


def create_plot():
    p = figure(width=800,
               height=600,
               x_range=(-10, 110),
               y_range=(-10, 110),
               tools="pan,tap,wheel_zoom,box_zoom,reset,save")
    p.xaxis.major_tick_line_color = None  # turn off x-axis major ticks
    p.xaxis.minor_tick_line_color = None  # turn off x-axis minor ticks
    p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
    p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
    p.xaxis.major_label_text_font_size = '0pt'  # preferred method for removing tick labels
    p.yaxis.major_label_text_font_size = '0pt'  # preferred method for removing tick labels
    p.grid.grid_line_color = None
    p.outline_line_color = None
    p.sizing_mode = 'stretch_width'
    return p
