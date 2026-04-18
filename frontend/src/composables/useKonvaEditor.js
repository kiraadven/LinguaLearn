/**
 * useKonvaEditor — Canvas interaction composable
 * Manages element selection, drag, resize, rotate via Konva.Transformer
 */
import { ref, computed, nextTick } from 'vue'

export function useKonvaEditor(timelineComposable, getCurrentPartId = null) {
  const { updateElement, getElementById, updatePartElement, getPartElement } = timelineComposable

  // ── State ──
  const selectedElementId = ref(null)
  const canvasZoom = ref(1.0)
  const stageRef = ref(null)
  const transformerRef = ref(null)

  // Currently selected element — returns merged (part overrides + global) when a part is active
  const selectedElement = computed(() => {
    if (!selectedElementId.value) return null
    const partId = getCurrentPartId?.()
    if (partId && getPartElement) {
      return getPartElement(partId, selectedElementId.value)
    }
    return getElementById(selectedElementId.value)
  })

  // ── Selection ──

  function selectElement(elementId) {
    selectedElementId.value = elementId
    nextTick(() => attachTransformer())
  }

  function clearSelection() {
    selectedElementId.value = null
    detachTransformer()
  }

  function attachTransformer() {
    if (!transformerRef.value || !selectedElementId.value) return

    const transformer = transformerRef.value.getNode()
    const stage = stageRef.value?.getStage()
    if (!stage || !transformer) return

    // Find the Konva Group node with matching id
    const targetNode = stage.findOne(`#${selectedElementId.value}`)
    if (targetNode) {
      transformer.nodes([targetNode])
      transformer.getLayer()?.batchDraw()
    }
  }

  function detachTransformer() {
    if (!transformerRef.value) return
    const transformer = transformerRef.value.getNode()
    if (transformer) {
      transformer.nodes([])
      transformer.getLayer()?.batchDraw()
    }
  }

  // ── Drag & Transform Handlers ──

  function _updateEl(elementId, patch) {
    const partId = getCurrentPartId?.()
    if (partId && updatePartElement) {
      updatePartElement(partId, elementId, patch)
    } else {
      updateElement(elementId, patch)
    }
  }

  /**
   * Handle element drag end — update position in timeline (per-part)
   */
  function onDragEnd(elementId, event) {
    const node = event.target
    const stage = stageRef.value?.getStage()
    if (!node || !stage) return

    const stageW = stage.width()
    const stageH = stage.height()

    // Convert pixel position back to normalized 0-1
    const x = Math.max(0, Math.min(1, node.x() / stageW))
    const y = Math.max(0, Math.min(1, node.y() / stageH))

    _updateEl(elementId, { position: { x, y } })
  }

  /**
   * Handle element transform end — update size, rotation in timeline (per-part)
   */
  function onTransformEnd(elementId, event) {
    const node = event.target
    const stage = stageRef.value?.getStage()
    if (!node || !stage) return

    const stageW = stage.width()
    const stageH = stage.height()

    const scaleX = node.scaleX()
    const scaleY = node.scaleY()

    const newW = (node.width() * scaleX) / stageW
    const newH = (node.height() * scaleY) / stageH
    const newX = node.x() / stageW
    const newY = node.y() / stageH

    node.scaleX(1)
    node.scaleY(1)

    _updateEl(elementId, {
      position: { x: newX, y: newY },
      size: { w: Math.max(0.03, newW), h: Math.max(0.02, newH) },
      rotation: node.rotation() || 0,
    })
  }

  // ── Canvas Zoom ──

  function zoomIn() {
    canvasZoom.value = Math.min(2.0, canvasZoom.value + 0.1)
  }

  function zoomOut() {
    canvasZoom.value = Math.max(0.3, canvasZoom.value - 0.1)
  }

  function zoomReset() {
    canvasZoom.value = 1.0
  }

  // ── Stage Click (deselect) ──

  function onStageClick(event) {
    // If clicked on empty stage area, deselect
    if (event.target === event.target.getStage()) {
      clearSelection()
    }
  }

  // ── Transformer Config ──
  const transformerConfig = computed(() => ({
    // Appearance
    borderStroke: '#7c3aed',
    borderStrokeWidth: 2,
    anchorStroke: '#7c3aed',
    anchorFill: '#fff',
    anchorSize: 8,
    anchorCornerRadius: 2,
    rotateAnchorOffset: 20,
    enabledAnchors: [
      'top-left', 'top-right', 'bottom-left', 'bottom-right',
      'middle-left', 'middle-right', 'top-center', 'bottom-center',
    ],
    keepRatio: false,
    // Rotation
    rotateEnabled: true,
    // Bounds
    boundBoxFunc: (oldBox, newBox) => {
      // Minimum size: 20x20 pixels
      if (newBox.width < 20 || newBox.height < 20) return oldBox
      return newBox
    },
  }))

  return {
    // State
    selectedElementId,
    selectedElement,
    canvasZoom,
    stageRef,
    transformerRef,

    // Actions
    selectElement,
    clearSelection,
    onDragEnd,
    onTransformEnd,
    onStageClick,

    // Zoom
    zoomIn,
    zoomOut,
    zoomReset,

    // Config
    transformerConfig,
  }
}
