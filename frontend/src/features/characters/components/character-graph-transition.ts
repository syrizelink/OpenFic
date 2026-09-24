import type { Edge, Node, XYPosition } from "@xyflow/react";

interface GraphMove {
  id: string;
  from: XYPosition;
  to: XYPosition;
}

export function interpolateGraphPosition(
  from: XYPosition,
  to: XYPosition,
  progress: number,
): XYPosition {
  const elapsed = Math.max(0, Math.min(progress, 1));
  const eased = elapsed < 0.5 ? 4 * elapsed ** 3 : 1 - (-2 * elapsed + 2) ** 3 / 2;
  return { x: from.x + (to.x - from.x) * eased, y: from.y + (to.y - from.y) * eased };
}

export function planGraphTransition<N extends Node, E extends Edge>(
  currentNodes: N[],
  nextNodes: N[],
  currentEdges: E[],
  nextEdges: E[],
  animate: boolean,
): { nodes: N[]; edges: E[]; moves: GraphMove[] } {
  if (!animate) return { nodes: nextNodes, edges: nextEdges, moves: [] };

  const previousNodes = new Map(currentNodes.map((node) => [node.id, node]));
  const nextNodeIds = new Set(nextNodes.map((node) => node.id));
  const previousEdges = new Set(currentEdges.map((edge) => edge.id));
  const nextEdgeIds = new Set(nextEdges.map((edge) => edge.id));
  const moves: GraphMove[] = [];

  const nodes = nextNodes.map((node) => {
    const previous = previousNodes.get(node.id);
    const neighbor = nextEdges.find((edge) =>
      edge.source === node.id
        ? previousNodes.has(edge.target)
        : edge.target === node.id && previousNodes.has(edge.source),
    );
    const origin =
      previous?.position ??
      (neighbor
        ? previousNodes.get(neighbor.source === node.id ? neighbor.target : neighbor.source)
            ?.position
        : undefined) ??
      node.position;

    if (origin.x !== node.position.x || origin.y !== node.position.y) {
      moves.push({ id: node.id, from: origin, to: node.position });
    }
    return {
      ...node,
      position: origin,
      className: previous ? node.className : "character-graph-entering",
    } as N;
  });

  nodes.push(
    ...currentNodes
      .filter((node) => !nextNodeIds.has(node.id))
      .map(
        (node) =>
          ({
            ...node,
            className: "character-graph-exiting",
          }) as N,
      ),
  );

  const edges = nextEdges.map(
    (edge) =>
      ({
        ...edge,
        className: previousEdges.has(edge.id) ? edge.className : "character-graph-entering",
      }) as E,
  );
  edges.push(
    ...currentEdges
      .filter((edge) => !nextEdgeIds.has(edge.id))
      .map(
        (edge) =>
          ({
            ...edge,
            className: "character-graph-exiting",
          }) as E,
      ),
  );

  return { nodes, edges, moves };
}
