import { ExcalidrawElement } from "../element/types";

/**
 * Serializes the current active Excalidraw canvas elements into a structured, compact
 * textual representation representing shapes, text, and connections (arrows) for LLM consumption.
 */
export const serializeCanvas = (
  elements: readonly ExcalidrawElement[],
): string => {
  const activeElements = elements.filter((el) => !el.isDeleted);

  const containerToText = new Map<string, string>();
  const freeText: string[] = [];
  const elementMap = new Map<string, ExcalidrawElement>();

  // 1. First pass: map elements and link bound text elements to their shape containers
  activeElements.forEach((el) => {
    elementMap.set(el.id, el);
    if (el.type === "text") {
      const textVal = (el as any).text || "";
      const containerId = (el as any).containerId;
      if (containerId) {
        containerToText.set(containerId, textVal);
      } else {
        freeText.push(
          `"${textVal}" at (${Math.round(el.x)}, ${Math.round(el.y)})`,
        );
      }
    }
  });

  const shapes: string[] = [];
  const arrows: string[] = [];

  // 2. Second pass: describe shapes and their content, and resolve arrows relations
  activeElements.forEach((el) => {
    if (
      el.type === "rectangle" ||
      el.type === "ellipse" ||
      el.type === "diamond"
    ) {
      const boundText = containerToText.get(el.id);
      const label = boundText ? `"${boundText}"` : "empty shape";
      const rx = Math.round(el.x);
      const ry = Math.round(el.y);
      const rw = Math.round(el.width);
      const rh = Math.round(el.height);
      shapes.push(
        `- Shape (${el.type}): ${label} at (${rx}, ${ry}) size ${rw}x${rh}`,
      );
    } else if (el.type === "freedraw" || el.type === "line") {
      const rx = Math.round(el.x);
      const ry = Math.round(el.y);
      const rw = Math.round(el.width);
      const rh = Math.round(el.height);
      shapes.push(
        `- Freehand Stroke (${el.type}) at (${rx}, ${ry}) size ${rw}x${rh}`,
      );
    } else if (el.type === "arrow") {
      const startId = (el as any).startBinding?.elementId;
      const endId = (el as any).endBinding?.elementId;

      let relation = "";
      if (startId && endId) {
        const startEl = elementMap.get(startId);
        const endEl = elementMap.get(endId);

        const startLabel = startEl
          ? containerToText.get(startId) ||
            (startEl as any).text ||
            startEl.type
          : "unknown";
        const endLabel = endEl
          ? containerToText.get(endId) || (endEl as any).text || endEl.type
          : "unknown";
        relation = ` (connecting "${startLabel}" -> "${endLabel}")`;
      }
      arrows.push(
        `- Arrow${relation} at (${Math.round(el.x)}, ${Math.round(el.y)})`,
      );
    } else if (el.type === "image") {
      const rx = Math.round(el.x);
      const ry = Math.round(el.y);
      const rw = Math.round(el.width);
      const rh = Math.round(el.height);
      shapes.push(
        `- [Image pasted at (${rx}, ${ry}), size ${rw}x${rh} — image content is not visible to the interviewer, only its position and size]`,
      );
    }
  });

  // Compile segments
  const segments = [];
  if (shapes.length > 0) {
    segments.push(`Shapes & Bounding Boxes:\n${shapes.join("\n")}`);
  }
  if (arrows.length > 0) {
    segments.push(`Connections & Flows:\n${arrows.join("\n")}`);
  }
  if (freeText.length > 0) {
    segments.push(
      `Freeform Labels & Code:\n${freeText.map((t) => `- ${t}`).join("\n")}`,
    );
  }

  return segments.join("\n\n");
};
