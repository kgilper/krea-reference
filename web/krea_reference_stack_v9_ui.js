// ComfyUI frontend extension for the KG Krea 2 V9 nodes.
//
// Stack encoder: keeps the reference-card inputs compact while the backend
// still validates up to 12 cards.
//
// Guide card: greys out the manual-only rows whenever "Use image for" is a
// quick recipe, so it is visible at a glance that only "manual tuning" reads
// those widgets.
import { app } from "/scripts/app.js";

const REFERENCE_TYPE = "KG_KREA_REFERENCE";
const MAX_REFERENCE_CARDS = 12;

const STACK_NODES = {
  KGTextEncodeKreaImageReferencesV9: {
    marker: "__kgKreaV9StackUi",
    patched: "__kgKreaV9StackPatched",
    inputPattern: /^Reference \d+ guide card$/,
    inputName: (i) => `Reference ${i} guide card`,
  },
};

const GUIDE_CARD_NODES = {
  KGKrea2ImageGuideCardV9: {
    marker: "__kgKreaV9CardUi",
    patched: "__kgKreaV9CardPatched",
    purposeWidget: "Use image for",
    manualValue: "manual tuning",
    manualOnlyWidgets: [
      "Manual mode borrows",
      "Prepare image by",
      "Color kept",
      "Small details kept",
      "Study this image at",
      "Frame this reference by",
      "Subject copying",
      "Early layout guidance",
      "Final detail copying",
      "Maximum image pull",
      "Shape copied",
      "Overall style reach",
    ],
  },
};

function getStackConfig(value) {
  return STACK_NODES[value] || null;
}

function getStackNodeConfig(node) {
  return getStackConfig(node?.type) || getStackConfig(node?.comfyClass);
}

function getCardConfig(value) {
  return GUIDE_CARD_NODES[value] || null;
}

function getCardNodeConfig(node) {
  return getCardConfig(node?.type) || getCardConfig(node?.comfyClass);
}

// ---------------------------------------------------------------------------
// Stack encoder: compact reference-card sockets
// ---------------------------------------------------------------------------

function isReferenceInput(input, config) {
  return config.inputPattern.test(input?.name || "");
}

function inputHasLink(input) {
  return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0);
}

function getReferenceInputs(node) {
  const config = getStackNodeConfig(node);
  if (!config) return [];
  return (node.inputs || [])
    .map((input, index) => ({ input, index }))
    .filter(({ input }) => isReferenceInput(input, config));
}

function normalizeReferenceInputs(node) {
  const config = getStackNodeConfig(node);
  if (!config) return;
  const refs = getReferenceInputs(node);
  refs.forEach(({ input }, i) => {
    input.name = config.inputName(i + 1);
    input.type = REFERENCE_TYPE;
  });
}

function stabilizeReferenceInputs(node) {
  if (!getStackNodeConfig(node)) return;

  normalizeReferenceInputs(node);
  let refs = getReferenceInputs(node);

  let highestConnected = -1;
  refs.forEach(({ input }, i) => {
    if (inputHasLink(input)) highestConnected = i;
  });

  const desiredCount = Math.min(
    MAX_REFERENCE_CARDS,
    Math.max(1, highestConnected + 2)
  );

  for (let i = refs.length - 1; i >= desiredCount; i--) {
    const { input, index } = refs[i];
    if (!inputHasLink(input)) {
      node.removeInput(index);
    }
  }

  normalizeReferenceInputs(node);
  refs = getReferenceInputs(node);

  while (refs.length < desiredCount) {
    const config = getStackNodeConfig(node);
    node.addInput(config.inputName(refs.length + 1), REFERENCE_TYPE);
    refs = getReferenceInputs(node);
  }

  normalizeReferenceInputs(node);
  if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
}

function attachStackUi(node) {
  const config = getStackNodeConfig(node);
  if (!config || node[config.marker]) return;
  node[config.marker] = true;

  const previousOnConnectionsChange = node.onConnectionsChange;
  node.onConnectionsChange = function () {
    const result = previousOnConnectionsChange?.apply(this, arguments);
    setTimeout(() => stabilizeReferenceInputs(this), 0);
    return result;
  };

  setTimeout(() => stabilizeReferenceInputs(node), 50);
}

// ---------------------------------------------------------------------------
// Guide card: grey out manual-only widgets outside "manual tuning"
// ---------------------------------------------------------------------------

function findWidget(node, name) {
  return (node.widgets || []).find((w) => w?.name === name) || null;
}

function refreshManualWidgetState(node) {
  const config = getCardNodeConfig(node);
  if (!config) return;
  const purpose = findWidget(node, config.purposeWidget);
  if (!purpose) return;

  const manualActive = purpose.value === config.manualValue;
  for (const name of config.manualOnlyWidgets) {
    const widget = findWidget(node, name);
    if (!widget) continue;
    widget.disabled = !manualActive;
  }
  if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
}

function attachCardUi(node) {
  const config = getCardNodeConfig(node);
  if (!config || node[config.marker]) return;
  node[config.marker] = true;

  const purpose = findWidget(node, config.purposeWidget);
  if (purpose) {
    const previousCallback = purpose.callback;
    purpose.callback = function () {
      const result = previousCallback?.apply(this, arguments);
      refreshManualWidgetState(node);
      return result;
    };
  }

  // Configure runs after widget values load from a saved workflow.
  const previousOnConfigure = node.onConfigure;
  node.onConfigure = function () {
    const result = previousOnConfigure?.apply(this, arguments);
    setTimeout(() => refreshManualWidgetState(this), 0);
    return result;
  };

  setTimeout(() => refreshManualWidgetState(node), 50);
}

// ---------------------------------------------------------------------------

app.registerExtension({
  name: "kg.krea_reference_stack_v9_ui",

  beforeRegisterNodeDef(nodeType, nodeData) {
    const stackConfig = getStackConfig(nodeData?.name) || getStackConfig(nodeData?.comfyClass);
    if (stackConfig && !nodeType[stackConfig.patched]) {
      nodeType[stackConfig.patched] = true;
      const previousOnCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (previousOnCreated) previousOnCreated.apply(this, arguments);
        attachStackUi(this);
      };
    }

    const cardConfig = getCardConfig(nodeData?.name) || getCardConfig(nodeData?.comfyClass);
    if (cardConfig && !nodeType[cardConfig.patched]) {
      nodeType[cardConfig.patched] = true;
      const previousOnCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (previousOnCreated) previousOnCreated.apply(this, arguments);
        attachCardUi(this);
      };
    }
  },

  nodeCreated(node) {
    attachStackUi(node);
    attachCardUi(node);
  },
});
