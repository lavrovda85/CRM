"use client";

import { type ReactNode } from "react";
import {
  DragDropContext,
  Droppable,
  Draggable,
  type DropResult,
} from "@hello-pangea/dnd";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface KanbanColumn {
  id: string;
  title: string;
  color: string;
}

export interface KanbanCard {
  id: string;
  title: string;
  subtitle?: string;
  badges?: { label: string; color: string }[];
  avatar?: string;
  progress?: number;
}

export interface KanbanBoardProps {
  /** Определения колонок. */
  columns: KanbanColumn[];
  /** Карточки, сгруппированные по ID колонки. */
  cards: Record<string, KanbanCard[]>;
  /** Callback перемещения карточки между колонками. */
  onCardMove?: (cardId: string, fromCol: string, toCol: string) => void;
  /** Callback клика по карточке. */
  onCardClick?: (cardId: string) => void;
  /** Кастомный рендер карточки. */
  renderCard?: (card: KanbanCard) => ReactNode;
}

/* ------------------------------------------------------------------ */
/*  Default card                                                       */
/* ------------------------------------------------------------------ */

function DefaultCard({
  card,
  onClick,
}: {
  card: KanbanCard;
  onClick?: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick?.()}
      className="rounded-lg border border-surface-200 bg-white p-3 shadow-sm hover:shadow-md hover:border-primary-200 transition-all cursor-pointer group"
    >
      <p className="text-sm font-medium text-surface-800 group-hover:text-primary-700 line-clamp-2">
        {card.title}
      </p>

      {card.subtitle && (
        <p className="mt-1 text-xs text-surface-500 line-clamp-1">{card.subtitle}</p>
      )}

      {card.badges && card.badges.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {card.badges.map((b) => (
            <span
              key={b.label}
              className="inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium"
              style={{ backgroundColor: `${b.color}20`, color: b.color }}
            >
              {b.label}
            </span>
          ))}
        </div>
      )}

      {card.progress !== undefined && (
        <div className="mt-2">
          <div className="h-1.5 w-full rounded-full bg-surface-100">
            <div
              className="h-1.5 rounded-full bg-primary-500 transition-all"
              style={{ width: `${Math.min(100, Math.max(0, card.progress))}%` }}
            />
          </div>
        </div>
      )}

      {card.avatar && (
        <div className="mt-2 flex justify-end">
          <div className="h-6 w-6 rounded-full bg-surface-200 overflow-hidden">
            <img src={card.avatar} alt="" className="h-full w-full object-cover" />
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Board                                                              */
/* ------------------------------------------------------------------ */

/**
 * Универсальная канбан-доска с drag-and-drop и адаптивной горизонтальной прокруткой.
 *
 * Args:
 *     columns: Массив определений колонок.
 *     cards: Объект, где ключ — ID колонки, значение — массив карточек.
 *     onCardMove: Callback при перемещении карточки.
 *     onCardClick: Callback при клике по карточке.
 *     renderCard: Кастомная функция рендеринга карточки.
 *
 * Returns:
 *     JSX-элемент канбан-доски.
 */
export function KanbanBoard({
  columns,
  cards,
  onCardMove,
  onCardClick,
  renderCard,
}: KanbanBoardProps) {
  const handleDragEnd = (result: DropResult) => {
    const { draggableId, source, destination } = result;
    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;
    onCardMove?.(draggableId, source.droppableId, destination.droppableId);
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory scrollbar-thin">
        {columns.map((col) => {
          const colCards = cards[col.id] ?? [];
          return (
            <div
              key={col.id}
              className="flex-shrink-0 w-72 snap-start"
            >
              {/* Column header */}
              <div className="mb-3 flex items-center gap-2">
                <div
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: col.color }}
                />
                <h3 className="text-sm font-semibold text-surface-700">{col.title}</h3>
                <span className="ml-auto rounded-full bg-surface-100 px-2 py-0.5 text-xs font-medium text-surface-500">
                  {colCards.length}
                </span>
              </div>

              {/* Droppable area */}
              <Droppable droppableId={col.id}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={cn(
                      "min-h-[200px] space-y-2 rounded-xl p-2 transition-colors",
                      snapshot.isDraggingOver ? "bg-primary-50/60" : "bg-surface-50/50",
                    )}
                  >
                    {colCards.map((card, idx) => (
                      <Draggable key={card.id} draggableId={card.id} index={idx}>
                        {(dragProvided, dragSnapshot) => (
                          <div
                            ref={dragProvided.innerRef}
                            {...dragProvided.draggableProps}
                            {...dragProvided.dragHandleProps}
                            className={cn(
                              dragSnapshot.isDragging && "rotate-2 shadow-lg",
                            )}
                          >
                            {renderCard ? (
                              renderCard(card)
                            ) : (
                              <DefaultCard
                                card={card}
                                onClick={() => onCardClick?.(card.id)}
                              />
                            )}
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          );
        })}
      </div>
    </DragDropContext>
  );
}

export default KanbanBoard;
