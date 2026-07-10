const randomId = () => Math.random().toString(36).substring(2, 9);

interface PlanBlock {
  id: string;
  type: "code" | "diagram" | "note";
  title: string;
  content: string;
  addresses_gap: number | null;
  order: number;
}

interface PlanConnector {
  from_block_id: string;
  to_block_id: string;
  label: string;
}

interface StructuredPlan {
  blocks: PlanBlock[];
  connectors: PlanConnector[];
}

const createBaseElement = (
  type: string,
  x: number,
  y: number,
  width: number,
  height: number,
) => ({
  id: randomId(),
  type,
  x,
  y,
  width,
  height,
  strokeColor: "#1e1e24",
  backgroundColor: "transparent",
  fillStyle: "hachure",
  strokeWidth: 1,
  strokeStyle: "solid",
  roughness: 1,
  opacity: 100,
  isDeleted: false,
  seed: Math.floor(Math.random() * 100000),
  groupIds: [],
  roundness: type === "arrow" ? null : { type: 3 },
  boundElements: [],
  updated: Date.now(),
  link: null,
  locked: false,
});

export const structuredPlanToCanvasElements = (plan: StructuredPlan): any[] => {
  if (!plan || !plan.blocks) {
    return [];
  }

  const elements: any[] = [];
  const sortedBlocks = [...plan.blocks].sort((a, b) => a.order - b.order);

  // Coordinates mapping to draw connection lines
  const blockCoords: Record<
    string,
    { x: number; y: number; width: number; height: number }
  > = {};

  let currentY = 100;
  const blockWidth = 420;
  const paddingX = 150;
  const verticalGap = 120;

  sortedBlocks.forEach((block) => {
    // Estimate heights based on text rows
    const lines = `${block.title.toUpperCase()}\n\n${block.content}`.split(
      "\n",
    );
    const divisor = block.type === "code" ? 35 : 45;
    const lineCount = lines.reduce(
      (acc, line) => acc + Math.max(1, Math.ceil(line.length / divisor)),
      0,
    );
    const calculatedHeight = Math.max(
      140,
      lineCount * (block.type === "code" ? 24 : 22) + 50,
    );

    const x = paddingX;
    const y = currentY;

    // Save coordinate for connectors
    blockCoords[block.id] = {
      x,
      y,
      width: blockWidth,
      height: calculatedHeight,
    };

    // Create container shape (rectangle)
    const container = createBaseElement(
      "rectangle",
      x,
      y,
      blockWidth,
      calculatedHeight,
    );
    container.strokeWidth = 2;
    container.fillStyle = "solid";

    // Theme colors: yellow for note, blue/gray for code, light green/blue for diagram
    if (block.type === "note") {
      container.backgroundColor = "#fff9db"; // Yellow sticky note
      container.strokeColor = "#f59f00";
    } else if (block.type === "code") {
      container.backgroundColor = "#f8f9fa"; // Soft gray
      container.strokeColor = "#495057";
    } else {
      container.backgroundColor = "#e7f5ff"; // Soft blue
      container.strokeColor = "#1971c2";
    }

    // If block addresses a candidate gap, highlight the border
    if (block.addresses_gap !== null && block.addresses_gap !== undefined) {
      container.strokeColor = "#6965db"; // Deep violet accent
      container.strokeWidth = 3;
    }

    elements.push(container);

    // Create label text
    const displayText = `${block.title.toUpperCase()}\n\n${block.content}`;
    const textEl = createBaseElement(
      "text",
      x + 15,
      y + 15,
      blockWidth - 30,
      calculatedHeight - 30,
    );
    Object.assign(textEl, {
      text: displayText,
      fontSize: 14,
      fontFamily: block.type === "code" ? 3 : 1, // 3 is Monospace, 1 is Sans-serif
      textAlign: "left",
      verticalAlign: "top",
      containerId: container.id,
      originalText: displayText,
      strokeColor: "#1e1e24",
    });

    elements.push(textEl);

    // If addresses_gap is set, draw a visual badge at the top-right corner of the block
    if (block.addresses_gap !== null && block.addresses_gap !== undefined) {
      const badgeX = x + blockWidth - 95;
      const badgeY = y - 10;
      const badgeWidth = 90;
      const badgeHeight = 22;

      const badgeContainer = createBaseElement(
        "rectangle",
        badgeX,
        badgeY,
        badgeWidth,
        badgeHeight,
      );
      badgeContainer.backgroundColor = "#eef2ff";
      badgeContainer.strokeColor = "#6965db";
      badgeContainer.strokeWidth = 1.5;
      badgeContainer.fillStyle = "solid";
      elements.push(badgeContainer);

      const badgeText = createBaseElement(
        "text",
        badgeX + 4,
        badgeY + 4,
        badgeWidth - 8,
        badgeHeight - 8,
      );
      Object.assign(badgeText, {
        text: `FIXES CITE #${block.addresses_gap}`,
        fontSize: 10,
        fontFamily: 1,
        textAlign: "center",
        verticalAlign: "middle",
        strokeColor: "#6965db",
      });
      elements.push(badgeText);

      // Store reference link on container to identify click target
      (container as any).customAddressesGap = block.addresses_gap;
    }

    currentY += calculatedHeight + verticalGap;
  });

  // Create connector lines/arrows
  const connectors = plan.connectors || [];
  connectors.forEach((conn) => {
    const from = blockCoords[conn.from_block_id];
    const to = blockCoords[conn.to_block_id];

    if (from && to) {
      const startX = from.x + from.width / 2;
      const startY = from.y + from.height;
      const endX = to.x + to.width / 2;
      const endY = to.y;

      const arrow = createBaseElement("arrow", startX, startY, 0, 0);
      Object.assign(arrow, {
        points: [
          [0, 0],
          [endX - startX, endY - startY],
        ],
        strokeColor: "#6965db",
        strokeWidth: 2,
      });
      elements.push(arrow);

      // Draw label text next to arrow center
      if (conn.label) {
        const midX = (startX + endX) / 2 - 50;
        const midY = (startY + endY) / 2 - 10;

        const labelText = createBaseElement("text", midX, midY, 100, 20);
        Object.assign(labelText, {
          text: conn.label,
          fontSize: 11,
          fontFamily: 1,
          textAlign: "center",
          verticalAlign: "middle",
          strokeColor: "#6965db",
        });
        elements.push(labelText);
      }
    }
  });

  return elements;
};
