import { Avatar, IconButton, Popover, Text, Tooltip } from "@radix-ui/themes";
import { ChevronRight } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { CharacterGraph, CharacterRelationship } from "@/lib/character.types";

interface CharacterRelationshipListProps {
  characterId: string;
  nodes: Pick<CharacterGraph["nodes"][number], "characterId" | "name" | "imageUrl">[];
  relationships: CharacterRelationship[];
}

interface CharacterRelationshipItemProps {
  character: Pick<CharacterGraph["nodes"][number], "name" | "imageUrl"> | undefined;
  relationship: CharacterRelationship;
}

function CharacterRelationshipItem({ character, relationship }: CharacterRelationshipItemProps) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const descriptionId = useId();
  const name = character?.name ?? "?";

  return (
    <div
      className="characters-relationships-item"
      data-expanded={isExpanded}
    >
      <div className="characters-relationships-summary">
        <Tooltip
          content={t(
            isExpanded
              ? "characters.graph.collapseRelationship"
              : "characters.graph.expandRelationship",
          )}
        >
          <IconButton
            size="1"
            variant="ghost"
            color="gray"
            className="characters-relationships-toggle"
            aria-label={t(
              isExpanded
                ? "characters.graph.collapseRelationship"
                : "characters.graph.expandRelationship",
            )}
            aria-expanded={isExpanded}
            aria-controls={descriptionId}
            onClick={() => setIsExpanded((expanded) => !expanded)}
          >
            <ChevronRight size={14} />
          </IconButton>
        </Tooltip>
        <Avatar
          size="1"
          radius="full"
          src={character?.imageUrl ?? undefined}
          fallback={name.slice(0, 1)}
        />
        <span
          className="characters-relationships-person"
          title={name}
        >
          {name}
        </span>
        <span
          className="characters-relationships-name"
          title={relationship.name}
        >
          {relationship.name}
        </span>
      </div>
      <div
        id={descriptionId}
        className="characters-relationships-body"
        aria-hidden={!isExpanded}
      >
        <div className="characters-relationships-body-inner">
          <Text
            as="p"
            size="1"
            className="characters-relationships-description"
          >
            {relationship.description || t("characters.graph.noDescription")}
          </Text>
        </div>
      </div>
    </div>
  );
}

export function CharacterRelationshipList({
  characterId,
  nodes,
  relationships,
}: CharacterRelationshipListProps) {
  const { t } = useTranslation();
  const nodeById = new Map(nodes.map((node) => [node.characterId, node]));
  const related = relationships.filter(
    (relation) =>
      relation.sourceCharacterId === characterId || relation.targetCharacterId === characterId,
  );

  if (related.length === 0)
    return (
      <Text className="characters-relationships-empty">
        {t("characters.graph.noRelationships")}
      </Text>
    );

  return (
    <div className="characters-relationships-list">
      {related.map((relation) => {
        const relatedCharacterId =
          relation.sourceCharacterId === characterId
            ? relation.targetCharacterId
            : relation.sourceCharacterId;
        return (
          <CharacterRelationshipItem
            key={relation.id}
            character={nodeById.get(relatedCharacterId)}
            relationship={relation}
          />
        );
      })}
    </div>
  );
}

interface CharacterRelationshipsProps {
  characterId: string;
  count: number;
  graph: CharacterGraph | undefined;
}

export function CharacterRelationships({ characterId, count, graph }: CharacterRelationshipsProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const handleEnter = () => {
    clearTimeout(closeTimer.current);
    setIsOpen(true);
  };
  const handleLeave = () => {
    closeTimer.current = setTimeout(() => setIsOpen(false), 180);
  };

  if (count <= 0) return null;

  return (
    <Popover.Root
      open={isOpen}
      onOpenChange={setIsOpen}
    >
      <Popover.Trigger>
        <button
          type="button"
          className="characters-relationship-badge"
          aria-label={t("characters.graph.relationshipCount", { count })}
          onPointerEnter={(event) => {
            if (event.pointerType === "mouse") handleEnter();
          }}
          onPointerLeave={(event) => {
            if (event.pointerType === "mouse") handleLeave();
          }}
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          {count}
        </button>
      </Popover.Trigger>
      <Popover.Content
        side="right"
        align="start"
        sideOffset={8}
        className="characters-relationships-panel"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        onPointerEnter={(event) => {
          if (event.pointerType === "mouse") handleEnter();
        }}
        onPointerLeave={(event) => {
          if (event.pointerType === "mouse") handleLeave();
        }}
      >
        <CharacterRelationshipList
          characterId={characterId}
          nodes={graph?.nodes ?? []}
          relationships={graph?.relationships ?? []}
        />
      </Popover.Content>
    </Popover.Root>
  );
}
