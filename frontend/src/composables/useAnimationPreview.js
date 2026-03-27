/**
 * useAnimationPreview — animation preview playback composable
 */
import { ref } from 'vue'
import { applyEnterAnimation, applyExitAnimation, ANIMATION_PRESETS } from '@shared/animation-engine.js'

export function useAnimationPreview(stageRef) {
  const isPlaying = ref(false)
  const activeTweens = ref([])

  /**
   * Play enter animation on all nodes in the current layer
   */
  async function playEnterAnimation(elementNodes, Konva) {
    if (isPlaying.value) return
    isPlaying.value = true

    // Stop any existing tweens
    stopAll()

    const promises = []

    for (const { nodeRef, animation } of elementNodes) {
      if (!nodeRef || !animation?.enter) continue

      const node = typeof nodeRef.getNode === 'function' ? nodeRef.getNode() : nodeRef
      if (!node) continue

      const promise = new Promise(resolve => {
        const tween = applyEnterAnimation(node, animation.enter, Konva, resolve)
        if (tween) {
          activeTweens.value.push(tween)
          tween.play()
        } else {
          resolve()
        }
      })
      promises.push(promise)
    }

    await Promise.all(promises)
    isPlaying.value = false
  }

  /**
   * Play exit animation on all nodes
   */
  async function playExitAnimation(elementNodes, Konva) {
    if (isPlaying.value) return
    isPlaying.value = true

    stopAll()

    const promises = []

    for (const { nodeRef, animation } of elementNodes) {
      if (!nodeRef || !animation?.exit) continue

      const node = typeof nodeRef.getNode === 'function' ? nodeRef.getNode() : nodeRef
      if (!node) continue

      const promise = new Promise(resolve => {
        const tween = applyExitAnimation(node, animation.exit, Konva, resolve)
        if (tween) {
          activeTweens.value.push(tween)
          tween.play()
        } else {
          resolve()
        }
      })
      promises.push(promise)
    }

    await Promise.all(promises)
    isPlaying.value = false
  }

  /**
   * Stop all active animations
   */
  function stopAll() {
    for (const tween of activeTweens.value) {
      try { tween.destroy() } catch {}
    }
    activeTweens.value = []
  }

  /**
   * Reset all nodes to fully visible, no offset
   */
  function resetNodes(elementNodes) {
    for (const { nodeRef } of elementNodes) {
      const node = typeof nodeRef.getNode === 'function' ? nodeRef.getNode() : nodeRef
      if (!node) continue
      node.opacity(1)
      node.scaleX(1)
      node.scaleY(1)
      node.offsetX(0)
      node.offsetY(0)
    }
    if (stageRef.value) {
      const stage = stageRef.value.getStage?.() || stageRef.value
      stage?.batchDraw?.()
    }
  }

  return {
    isPlaying,
    playEnterAnimation,
    playExitAnimation,
    stopAll,
    resetNodes,
    ANIMATION_PRESETS,
  }
}
