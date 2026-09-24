import {
  AlertDialog,
  Button,
  Dialog,
  Flex,
  IconButton,
  Text,
  TextArea,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Background,
  ControlButton,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useOnViewportChange,
  useReactFlow,
  useStore,
  useStoreApi,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type Viewport,
} from "@xyflow/react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import {
  ChevronDown,
  ChevronUp,
  Crosshair,
  Lock,
  Maximize,
  Minus,
  Orbit,
  Plus,
  Search,
  Unlock,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/components/toast";
import {
  createCharacterRelationship,
  deleteCharacterRelationship,
  fetchCharacterGraph,
  updateCharacterPosition,
  updateCharacterRelationship,
} from "@/lib/api-client";
import type { CharacterGraph, CharacterRelationship } from "@/lib/character.types";
import { getPreference, setPreference } from "@/lib/local-db";

import { interpolateGraphPosition, planGraphTransition } from "./character-graph-transition";

import "@xyflow/react/dist/style.css";
import "./character-graph.css";

interface CharacterNodeData extends Record<string, unknown> {
  label: string;
  imageUrl: string | null;
  count: number;
}

type CharacterNode = Node<CharacterNodeData, "character">;

interface LayoutNode extends SimulationNodeDatum {
  id: string;
  width: number;
  height: number;
  radius: number;
}

const TRANSITION_DURATION = 360;
const MIN_GRAPH_ZOOM = 0.15;
const MAX_GRAPH_ZOOM = 2.5;

function parseGraphViewport(value: string | null): Viewport | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed !== "object" || parsed === null) return null;
    const viewport = parsed as Partial<Viewport>;
    if (
      typeof viewport.x !== "number" ||
      !Number.isFinite(viewport.x) ||
      typeof viewport.y !== "number" ||
      !Number.isFinite(viewport.y) ||
      typeof viewport.zoom !== "number" ||
      !Number.isFinite(viewport.zoom) ||
      viewport.zoom < MIN_GRAPH_ZOOM ||
      viewport.zoom > MAX_GRAPH_ZOOM
    )
      return null;
    return { x: viewport.x, y: viewport.y, zoom: viewport.zoom };
  } catch {
    return null;
  }
}

function GraphViewportPersistence({ preferenceKey }: { preferenceKey: string }) {
  const latestViewportRef = useRef<Viewport | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useOnViewportChange({
    onEnd: (viewport) => {
      latestViewportRef.current = viewport;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null;
        void setPreference(preferenceKey, JSON.stringify(viewport));
      }, 250);
    },
  });

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
        const viewport = latestViewportRef.current;
        if (viewport) void setPreference(preferenceKey, JSON.stringify(viewport));
      }
    };
  }, [preferenceKey]);

  return null;
}

function CharacterAvatar({ imageUrl, name }: { imageUrl: string | null; name: string }) {
  const [displayed, setDisplayed] = useState(imageUrl);
  const [previous, setPrevious] = useState<string | null | undefined>(undefined);
  const [isReady, setIsReady] = useState(true);

  useEffect(() => {
    if (displayed === imageUrl) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplayed(imageUrl);
      setPrevious(undefined);
      return;
    }
    setPrevious(displayed);
    setDisplayed(imageUrl);
    setIsReady(imageUrl === null);
  }, [displayed, imageUrl]);

  useEffect(() => {
    if (previous === undefined || !isReady) return;
    const timeout = window.setTimeout(() => setPrevious(undefined), TRANSITION_DURATION + 40);
    return () => window.clearTimeout(timeout);
  }, [previous, isReady]);

  const renderAvatar = (
    url: string | null,
    className: string,
    onAnimationEnd?: () => void,
    isCurrent = false,
  ) =>
    url ? (
      <img
        key={url}
        src={url}
        alt=""
        className={className}
        onLoad={isCurrent ? () => setIsReady(true) : undefined}
        onError={isCurrent ? () => setIsReady(true) : undefined}
        onAnimationEnd={onAnimationEnd}
      />
    ) : (
      <span
        className={className}
        onAnimationEnd={onAnimationEnd}
      >
        {name.slice(0, 1)}
      </span>
    );

  return (
    <span className="character-graph-avatar-frame">
      {previous !== undefined &&
        renderAvatar(
          previous,
          `character-graph-avatar${isReady ? " character-graph-avatar--out" : ""}`,
          () => setPrevious(undefined),
        )}
      {renderAvatar(
        displayed,
        `character-graph-avatar${previous !== undefined ? (isReady ? " character-graph-avatar--in" : " character-graph-avatar--waiting") : ""}`,
        undefined,
        true,
      )}
    </span>
  );
}

function CharacterGraphNode({ data }: NodeProps<CharacterNode>) {
  return (
    <div
      className="character-graph-node"
      title={data.label}
    >
      <Handle
        type="target"
        position={Position.Left}
      />
      <CharacterAvatar
        imageUrl={data.imageUrl}
        name={data.label}
      />
      <span className="character-graph-node-name">{data.label}</span>
      <span className="character-graph-count">{data.count}</span>
      <Handle
        type="source"
        position={Position.Right}
      />
    </div>
  );
}

const nodeTypes = { character: CharacterGraphNode };

function SmoothGraphControls({
  isSearchOpen,
  onToggleSearch,
  onOpenSearch,
  graphRef,
  onAutoLayout,
  isAutoLayoutDisabled,
}: {
  isSearchOpen: boolean;
  onToggleSearch: () => void;
  onOpenSearch: () => void;
  graphRef: RefObject<HTMLDivElement | null>;
  onAutoLayout: () => void;
  isAutoLayoutDisabled: boolean;
}) {
  const { t } = useTranslation();
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const store = useStoreApi();
  const isInteractive = useStore(
    (state) => state.nodesDraggable || state.nodesConnectable || state.elementsSelectable,
  );
  const minZoomReached = useStore((state) => state.transform[2] <= state.minZoom);
  const maxZoomReached = useStore((state) => state.transform[2] >= state.maxZoom);
  const interactionLabel = t(isInteractive ? "characters.graph.lock" : "characters.graph.unlock");

  const handleToggleInteractivity = useCallback(() => {
    store.setState({
      nodesDraggable: !isInteractive,
      nodesConnectable: !isInteractive,
      elementsSelectable: !isInteractive,
    });
  }, [isInteractive, store]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.repeat) return;
      const target = event.target;
      const isInGraph = target instanceof HTMLElement && graphRef.current?.contains(target);
      const isTyping =
        target instanceof HTMLElement &&
        (target.isContentEditable || Boolean(target.closest("input, textarea, select")));
      if (target instanceof HTMLElement && target !== document.body && !isInGraph) return;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f" && !event.altKey) {
        event.preventDefault();
        onOpenSearch();
        return;
      }

      if (isTyping || event.ctrlKey || event.metaKey || event.altKey) return;

      switch (event.key.toLowerCase()) {
        case "+":
        case "=":
          if (maxZoomReached) return;
          event.preventDefault();
          void zoomIn({ duration: 350 });
          break;
        case "-":
        case "_":
          if (minZoomReached) return;
          event.preventDefault();
          void zoomOut({ duration: 350 });
          break;
        case "0":
          event.preventDefault();
          void fitView({ padding: 0.25, duration: 350 });
          break;
        case "l":
          event.preventDefault();
          handleToggleInteractivity();
          break;
        case "a":
          if (isAutoLayoutDisabled) return;
          event.preventDefault();
          onAutoLayout();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    fitView,
    graphRef,
    isAutoLayoutDisabled,
    handleToggleInteractivity,
    maxZoomReached,
    minZoomReached,
    onOpenSearch,
    onAutoLayout,
    zoomIn,
    zoomOut,
  ]);

  return (
    <Controls
      showZoom={false}
      showFitView={false}
      showInteractive={false}
    >
      <Tooltip
        content={`${t("characters.graph.zoomIn")} (+)`}
        side="right"
      >
        <ControlButton
          aria-label={t("characters.graph.zoomIn")}
          disabled={maxZoomReached}
          onClick={() => void zoomIn({ duration: 350 })}
        >
          <Plus />
        </ControlButton>
      </Tooltip>
      <Tooltip
        content={`${t("characters.graph.zoomOut")} (-)`}
        side="right"
      >
        <ControlButton
          aria-label={t("characters.graph.zoomOut")}
          disabled={minZoomReached}
          onClick={() => void zoomOut({ duration: 350 })}
        >
          <Minus />
        </ControlButton>
      </Tooltip>
      <Tooltip
        content={`${t("characters.graph.fit")} (0)`}
        side="right"
      >
        <ControlButton
          aria-label={t("characters.graph.fit")}
          onClick={() => void fitView({ padding: 0.25, duration: 350 })}
        >
          <Maximize />
        </ControlButton>
      </Tooltip>
      <Tooltip
        content={`${t("characters.graph.autoLayout")} (A)`}
        side="right"
      >
        <ControlButton
          aria-label={t("characters.graph.autoLayout")}
          disabled={isAutoLayoutDisabled}
          onClick={onAutoLayout}
        >
          <Orbit />
        </ControlButton>
      </Tooltip>
      <Tooltip
        content={`${interactionLabel} (L)`}
        side="right"
      >
        <ControlButton
          aria-label={interactionLabel}
          aria-pressed={!isInteractive}
          onClick={handleToggleInteractivity}
        >
          {isInteractive ? <Unlock /> : <Lock />}
        </ControlButton>
      </Tooltip>
      <Tooltip
        content={`${t("characters.graph.search")} (Ctrl+F)`}
        side="right"
      >
        <ControlButton
          aria-label={t("characters.graph.search")}
          aria-pressed={isSearchOpen}
          onClick={onToggleSearch}
        >
          <Search />
        </ControlButton>
      </Tooltip>
    </Controls>
  );
}

interface GraphProps {
  projectId: string;
  isLocked: boolean;
  onSelectCharacter: (characterId: string) => void;
}

function GraphCanvas({ projectId, isLocked, onSelectCharacter }: GraphProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { fitView, setCenter, getNodes, getEdges } = useReactFlow<CharacterNode, Edge>();
  const graphQueryKey = ["character-graph", projectId] as const;
  const viewportPreferenceKey = `character-graph-viewport:${projectId}`;
  const [viewportPreference, setViewportPreference] = useState<{
    key: string;
    viewport: Viewport | null;
  } | null>(null);
  const storedViewport =
    viewportPreference?.key === viewportPreferenceKey ? viewportPreference.viewport : undefined;
  const {
    data: graph,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: graphQueryKey,
    queryFn: () => fetchCharacterGraph(projectId),
  });
  const [nodes, setNodes, onNodesChange] = useNodesState<CharacterNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [search, setSearch] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const graphRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<{ source: string; target: string } | null>(null);
  const [editing, setEditing] = useState<CharacterRelationship | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isAutoLayoutRunning, setIsAutoLayoutRunning] = useState(false);
  const draggingIdRef = useRef<string | null>(null);
  const draggedDuringTransitionRef = useRef(new Set<string>());

  useEffect(() => {
    let isDiscarded = false;
    void getPreference(viewportPreferenceKey).then((value) => {
      if (isDiscarded) return;
      setViewportPreference({ key: viewportPreferenceKey, viewport: parseGraphViewport(value) });
    });
    return () => {
      isDiscarded = true;
    };
  }, [viewportPreferenceKey]);

  useEffect(() => {
    if (!graph) return;
    const nextNodes: CharacterNode[] = [...graph.nodes]
      .sort((a, b) => a.characterId.localeCompare(b.characterId))
      .map((item, index) => ({
        id: item.characterId,
        type: "character",
        position: {
          x: item.x ?? Math.cos(index * 2.399) * Math.sqrt(index + 1) * 140,
          y: item.y ?? Math.sin(index * 2.399) * Math.sqrt(index + 1) * 140,
        },
        data: { label: item.name, imageUrl: item.imageUrl, count: item.relationshipCount },
      }));
    const nextEdges: Edge[] = graph.relationships.map((relation) => ({
      id: relation.id,
      source: relation.sourceCharacterId,
      target: relation.targetCharacterId,
      label: relation.name,
      type: "default",
    }));
    const currentNodes = getNodes();
    const animate =
      currentNodes.length > 0 && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const transition = planGraphTransition(currentNodes, nextNodes, getEdges(), nextEdges, animate);
    setNodes(transition.nodes);
    setEdges(transition.edges);
    if (!animate) return;

    draggedDuringTransitionRef.current = new Set(
      draggingIdRef.current ? [draggingIdRef.current] : [],
    );
    const moves = new Map(transition.moves.map((move) => [move.id, move]));
    const remainingIds = new Set(nextNodes.map((node) => node.id));
    const startedAt = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / TRANSITION_DURATION, 1);
      setNodes((current) =>
        current.map((node) => {
          const move = moves.get(node.id);
          return move && !draggedDuringTransitionRef.current.has(node.id)
            ? { ...node, position: interpolateGraphPosition(move.from, move.to, progress) }
            : node;
        }),
      );
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        setNodes((current) =>
          current
            .filter((node) => remainingIds.has(node.id))
            .map((node) => ({
              ...node,
              className: undefined,
            })),
        );
        setEdges(nextEdges);
        draggedDuringTransitionRef.current.clear();
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [graph, getNodes, getEdges, setNodes, setEdges]);

  const closeForm = () => {
    setDraft(null);
    setEditing(null);
    setName("");
    setDescription("");
  };

  const handleConnect = (connection: Connection) => {
    if (
      isLocked ||
      !connection.source ||
      !connection.target ||
      connection.source === connection.target
    )
      return;
    if (
      graph?.relationships.some(
        (relation) =>
          [relation.sourceCharacterId, relation.targetCharacterId].includes(connection.source) &&
          [relation.sourceCharacterId, relation.targetCharacterId].includes(connection.target),
      )
    ) {
      toast.error(t("characters.graph.duplicate"));
      return;
    }
    setDraft({ source: connection.source, target: connection.target });
  };

  const handleSave = async () => {
    if (!name.trim() || isSaving) return;
    setIsSaving(true);
    try {
      if (editing) {
        await updateCharacterRelationship(editing.id, name.trim(), description);
      } else if (draft) {
        await createCharacterRelationship(projectId, {
          sourceCharacterId: draft.source,
          targetCharacterId: draft.target,
          name: name.trim(),
          description,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["character-graph", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["characters", projectId] });
      closeForm();
    } catch {
      toast.error(t("characters.graph.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!editing || isDeleting) return;
    setIsDeleting(true);
    try {
      await deleteCharacterRelationship(editing.id);
      await queryClient.invalidateQueries({ queryKey: ["character-graph", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["characters", projectId] });
      closeForm();
    } catch {
      toast.error(t("characters.graph.deleteFailed"));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleAutoLayout = async () => {
    if (isLocked || isAutoLayoutRunning) return;
    const currentNodes = getNodes().filter(
      (node) => !node.className?.split(" ").includes("character-graph-exiting"),
    );
    if (currentNodes.length === 0) return;

    setIsAutoLayoutRunning(true);
    try {
      const layoutNodes: LayoutNode[] = currentNodes.map((node) => {
        const width = node.measured?.width ?? 200;
        const height = node.measured?.height ?? 52;
        return {
          id: node.id,
          x: node.position.x + width / 2,
          y: node.position.y + height / 2,
          width,
          height,
          radius: Math.max(width, height) / 2 + 12,
        };
      });
      const nodeIds = new Set(layoutNodes.map((node) => node.id));
      const links: SimulationLinkDatum<LayoutNode>[] = getEdges()
        .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
        .map((edge) => ({ source: edge.source, target: edge.target }));
      const simulation = forceSimulation<LayoutNode, SimulationLinkDatum<LayoutNode>>(layoutNodes)
        .force(
          "link",
          forceLink<LayoutNode, SimulationLinkDatum<LayoutNode>>(links)
            .id((node) => node.id)
            .distance(240)
            .strength(0.35),
        )
        .force("charge", forceManyBody<LayoutNode>().strength(-200))
        .force(
          "collide",
          forceCollide<LayoutNode>()
            .radius((node) => node.radius)
            .strength(0.9)
            .iterations(2),
        )
        .force("x", forceX<LayoutNode>(0).strength(0.1))
        .force("y", forceY<LayoutNode>(0).strength(0.1))
        .force("center", forceCenter<LayoutNode>(0, 0))
        .alphaDecay(0.025)
        .stop();
      simulation.tick(260);

      const positions = new Map(
        layoutNodes.map((node) => [
          node.id,
          {
            x: (node.x ?? 0) - node.width / 2,
            y: (node.y ?? 0) - node.height / 2,
          },
        ]),
      );
      const layoutedNodes = currentNodes.map((node) => ({
        ...node,
        position: positions.get(node.id) ?? node.position,
      }));
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          position: positions.get(node.id) ?? node.position,
        })),
      );
      queryClient.setQueryData<CharacterGraph>(graphQueryKey, (current) => {
        if (!current) return current;
        return {
          ...current,
          nodes: current.nodes.map((node) => ({
            ...node,
            ...(positions.get(node.characterId) ?? {}),
          })),
        };
      });
      requestAnimationFrame(() => void fitView({ padding: 0.25, duration: 350 }));

      const saveResults = await Promise.allSettled(
        layoutedNodes.map((node) =>
          updateCharacterPosition(projectId, node.id, node.position.x, node.position.y),
        ),
      );
      if (saveResults.some((result) => result.status === "rejected")) {
        await queryClient.invalidateQueries({ queryKey: graphQueryKey });
        toast.error(t("characters.graph.saveFailed"));
      }
    } catch {
      toast.error(t("characters.graph.autoLayoutFailed"));
    } finally {
      setIsAutoLayoutRunning(false);
    }
  };

  const normalizedSearch = search.trim().toLowerCase();
  const matches = normalizedSearch
    ? [...(graph?.nodes ?? [])]
        .filter((node) => node.name.toLowerCase().includes(normalizedSearch))
        .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"))
    : [];
  const matchIds = new Set(matches.map((node) => node.characterId));
  const currentMatchId = matchIds.has(activeMatchId ?? "")
    ? activeMatchId
    : (matches[0]?.characterId ?? null);
  const currentMatchIndex = matches.findIndex((node) => node.characterId === currentMatchId);
  const visibleNodes = nodes.map((node) => ({
    ...node,
    className: [
      node.className,
      matchIds.has(node.id) && "character-graph-search-match",
      node.id === currentMatchId && "character-graph-search-active",
    ]
      .filter(Boolean)
      .join(" "),
  }));

  const locateMatch = (characterId: string) => {
    const node = getNodes().find((item) => item.id === characterId);
    if (!node) return;
    void setCenter(
      node.position.x + (node.measured?.width ?? 200) / 2,
      node.position.y + (node.measured?.height ?? 60) / 2,
      { zoom: 1.25, duration: 350 },
    );
  };

  const handleNavigateMatch = (direction: number) => {
    if (!matches.length) return;
    const next = matches[(currentMatchIndex + direction + matches.length) % matches.length];
    setActiveMatchId(next.characterId);
    locateMatch(next.characterId);
  };

  const handleCloseSearch = () => {
    setIsSearchOpen(false);
    setSearch("");
    setActiveMatchId(null);
  };

  useEffect(() => {
    if (isSearchOpen) searchInputRef.current?.focus();
  }, [isSearchOpen]);

  return (
    <div
      ref={graphRef}
      className="character-graph"
    >
      {isSearchOpen && (
        <div className="character-graph-search-bar">
          <TextField.Root
            ref={searchInputRef}
            size="2"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setActiveMatchId(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") handleCloseSearch();
              if (event.key === "Enter") handleNavigateMatch(event.shiftKey ? -1 : 1);
            }}
            placeholder={t("characters.graph.search")}
            aria-label={t("characters.graph.search")}
          />
          <Text
            size="1"
            className="character-graph-search-count"
          >
            {t("characters.graph.searchResults", {
              current: currentMatchIndex + 1,
              total: matches.length,
            })}
          </Text>
          <Tooltip content={t("characters.graph.previous")}>
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              disabled={!matches.length}
              aria-label={t("characters.graph.previous")}
              onClick={() => handleNavigateMatch(-1)}
            >
              <ChevronUp size={16} />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("characters.graph.next")}>
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              disabled={!matches.length}
              aria-label={t("characters.graph.next")}
              onClick={() => handleNavigateMatch(1)}
            >
              <ChevronDown size={16} />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("characters.graph.locate")}>
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              disabled={!currentMatchId}
              aria-label={t("characters.graph.locate")}
              onClick={() => {
                if (currentMatchId) locateMatch(currentMatchId);
              }}
            >
              <Crosshair size={16} />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("common.close")}>
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              aria-label={t("common.close")}
              onClick={handleCloseSearch}
            >
              <X size={16} />
            </IconButton>
          </Tooltip>
        </div>
      )}
      {isLoading && <Text className="character-graph-hint">{t("common.loading")}</Text>}
      {!isLoading && !isError && nodes.length === 0 && (
        <Text className="character-graph-hint">{t("characters.graph.empty")}</Text>
      )}
      {isError && (
        <div className="character-graph-hint">
          <Button onClick={() => void refetch()}>{t("characters.graph.loadFailed")}</Button>
        </div>
      )}
      {storedViewport !== undefined && (
        <ReactFlow
          nodes={visibleNodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={handleConnect}
          onNodeDoubleClick={(_event, node) => onSelectCharacter(node.id)}
          onEdgeClick={(_event, edge) => {
            const relation = graph?.relationships.find((item) => item.id === edge.id);
            if (!relation || isLocked) return;
            setEditing(relation);
            setName(relation.name);
            setDescription(relation.description);
          }}
          onNodeDragStop={(_event, node) => {
            draggingIdRef.current = null;
            queryClient.setQueryData<CharacterGraph>(graphQueryKey, (current) => {
              if (!current) return current;
              return {
                ...current,
                nodes: current.nodes.map((character) =>
                  character.characterId === node.id
                    ? { ...character, x: node.position.x, y: node.position.y }
                    : character,
                ),
              };
            });
            void updateCharacterPosition(
              projectId,
              node.id,
              node.position.x,
              node.position.y,
            ).catch(async () => {
              await queryClient.invalidateQueries({ queryKey: graphQueryKey });
              toast.error(t("characters.graph.saveFailed"));
            });
          }}
          onNodeDragStart={(_event, node) => {
            draggingIdRef.current = node.id;
            draggedDuringTransitionRef.current.add(node.id);
          }}
          nodesDraggable={!isLocked && !isAutoLayoutRunning}
          nodesConnectable={!isLocked && !isAutoLayoutRunning}
          deleteKeyCode={null}
          edgesFocusable
          elementsSelectable
          defaultViewport={storedViewport ?? { x: 0, y: 0, zoom: 1 }}
          fitView={storedViewport === null}
          fitViewOptions={{ padding: 0.25 }}
          minZoom={MIN_GRAPH_ZOOM}
          maxZoom={MAX_GRAPH_ZOOM}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <GraphViewportPersistence preferenceKey={viewportPreferenceKey} />
          <SmoothGraphControls
            isSearchOpen={isSearchOpen}
            graphRef={graphRef}
            onAutoLayout={() => void handleAutoLayout()}
            isAutoLayoutDisabled={isLocked || isAutoLayoutRunning || nodes.length === 0}
            onOpenSearch={() => {
              setIsSearchOpen(true);
              searchInputRef.current?.focus();
            }}
            onToggleSearch={() => {
              if (isSearchOpen) handleCloseSearch();
              else setIsSearchOpen(true);
            }}
          />
          <MiniMap
            pannable
            zoomable
          />
        </ReactFlow>
      )}
      <Dialog.Root
        open={Boolean(draft || editing)}
        onOpenChange={(open) => {
          if (!open) closeForm();
        }}
      >
        <Dialog.Content maxWidth="420px">
          <Dialog.Title>
            {editing ? t("characters.graph.edit") : t("characters.graph.create")}
          </Dialog.Title>
          <Flex
            direction="column"
            gap="3"
            mt="3"
          >
            <TextField.Root
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("characters.graph.name")}
              aria-label={t("characters.graph.name")}
              maxLength={200}
            />
            <TextArea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t("characters.graph.description")}
              aria-label={t("characters.graph.description")}
              maxLength={10000}
            />
            <Flex
              justify="between"
              align="center"
            >
              {editing ? (
                <AlertDialog.Root>
                  <AlertDialog.Trigger>
                    <Button
                      color="red"
                      variant="soft"
                    >
                      {t("common.delete")}
                    </Button>
                  </AlertDialog.Trigger>
                  <AlertDialog.Content maxWidth="360px">
                    <AlertDialog.Title>{t("characters.graph.deleteConfirm")}</AlertDialog.Title>
                    <Flex
                      justify="end"
                      gap="2"
                      mt="4"
                    >
                      <AlertDialog.Cancel>
                        <Button
                          variant="soft"
                          color="gray"
                        >
                          {t("common.cancel")}
                        </Button>
                      </AlertDialog.Cancel>
                      <AlertDialog.Action>
                        <Button
                          color="red"
                          disabled={isDeleting}
                          onClick={() => void handleDelete()}
                        >
                          {t("common.delete")}
                        </Button>
                      </AlertDialog.Action>
                    </Flex>
                  </AlertDialog.Content>
                </AlertDialog.Root>
              ) : (
                <span />
              )}
              <Flex gap="2">
                <Button
                  variant="soft"
                  color="gray"
                  onClick={closeForm}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  disabled={!name.trim() || isSaving}
                  onClick={() => void handleSave()}
                >
                  {t("common.save")}
                </Button>
              </Flex>
            </Flex>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </div>
  );
}

export function CharacterGraphView(props: GraphProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvas {...props} />
    </ReactFlowProvider>
  );
}
