import { useEffect, useCallback, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { PanelLeftOpen } from 'lucide-react'
import ReactFlow, {
  Background, Controls, MiniMap, useReactFlow, ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import toast from 'react-hot-toast'

import { useGraphStore } from '../../hooks/useGraphStore'
import { getAgent, createNode, createEdge, updateNode } from '../../api/client'
import { nodeTypes } from '../canvas/NodeTypes'
import { edgeTypes } from '../canvas/EdgeTypes'
import { NodePalette } from '../canvas/NodePalette'
import { ConfigPanel } from '../panels/ConfigPanel'
import { StateSchemaEditor } from '../panels/StateSchemaEditor'
import { RunModal } from '../panels/RunModal'
import { TopBar } from './TopBar'

let nodeCounter = 1
const DEFAULT_NODE_WIDTH = 220
const DEFAULT_NODE_HEIGHT = 110
const LAYOUT_COLUMN_GAP = 72
const LAYOUT_ROW_GAP = 110
const COMPONENT_GAP = 180

const getSuggestedNodeName = (nodes) => {
  const existingNames = new Set(
    nodes
      .map(node => String(node.data?.name || '').trim())
      .filter(Boolean)
  )

  let nextCounter = nodeCounter
  while (existingNames.has(`node_${nextCounter}`)) {
    nextCounter += 1
  }

  return `node_${nextCounter}`
}

const syncNodeCounter = (nodeName) => {
  const match = /^node_(\d+)$/.exec(String(nodeName || '').trim())
  if (!match) return

  nodeCounter = Math.max(nodeCounter, Number(match[1]) + 1)
}

const getNodeSize = (node) => ({
  width: node.width || node.measured?.width || DEFAULT_NODE_WIDTH,
  height: node.height || node.measured?.height || DEFAULT_NODE_HEIGHT,
})

const buildComponentLayout = ({ startIds, nodeMap, forwardAdjacency, incomingAdjacency, allowedIds, startY = 0 }) => {
  const allowed = new Set(allowedIds)
  const queue = [...startIds]
  const visited = new Set()
  const levels = new Map()
  const levelNodes = new Map()

  queue.forEach((id, index) => {
    if (!allowed.has(id)) return
    visited.add(id)
    levels.set(id, 0)
    levelNodes.set(0, [...(levelNodes.get(0) || []), id])
    queue[index] = id
  })

  let cursor = 0
  while (cursor < queue.length) {
    const nodeId = queue[cursor++]
    const level = levels.get(nodeId) || 0
    const nextIds = [...(forwardAdjacency.get(nodeId) || [])].sort((a, b) => {
      const aNode = nodeMap.get(a)
      const bNode = nodeMap.get(b)
      return (aNode?.position?.x || 0) - (bNode?.position?.x || 0)
    })

    nextIds.forEach((targetId) => {
      if (!allowed.has(targetId)) return
      const nextLevel = level + 1
      const currentLevel = levels.get(targetId)
      if (currentLevel == null || nextLevel < currentLevel) {
        levels.set(targetId, nextLevel)
      }
      if (visited.has(targetId)) return
      visited.add(targetId)
      queue.push(targetId)
    })
  }

  allowed.forEach((nodeId) => {
    if (levels.has(nodeId)) return
    const fallbackLevel = incomingAdjacency.get(nodeId)?.size ? 1 : 0
    levels.set(nodeId, fallbackLevel)
  })

  levels.forEach((level, nodeId) => {
    levelNodes.set(level, [...(levelNodes.get(level) || []), nodeId])
  })

  const orderedLevels = [...levelNodes.keys()].sort((a, b) => a - b)
  const positions = []
  let maxBottom = startY

  orderedLevels.forEach((level) => {
    const ids = [...new Set(levelNodes.get(level) || [])]
    const orderedIds = ids.sort((a, b) => {
      const parentIndex = (nodeId) => {
        const parents = [...(incomingAdjacency.get(nodeId) || [])].filter(parentId => levels.get(parentId) === level - 1)
        if (!parents.length) return nodeMap.get(nodeId)?.position?.x || 0
        const average = parents.reduce((sum, parentId) => sum + (nodeMap.get(parentId)?.position?.x || 0), 0) / parents.length
        return average
      }
      return parentIndex(a) - parentIndex(b)
    })

    const levelWidth = orderedIds.reduce((sum, nodeId, index) => {
      const { width } = getNodeSize(nodeMap.get(nodeId))
      return sum + width + (index > 0 ? LAYOUT_COLUMN_GAP : 0)
    }, 0)

    let currentX = -levelWidth / 2
    const levelY = startY + (level * (DEFAULT_NODE_HEIGHT + LAYOUT_ROW_GAP))
    let rowBottom = levelY

    orderedIds.forEach((nodeId) => {
      const node = nodeMap.get(nodeId)
      const { width, height } = getNodeSize(node)
      positions.push({
        id: nodeId,
        position: {
          x: Math.round(currentX),
          y: Math.round(levelY),
        },
      })
      currentX += width + LAYOUT_COLUMN_GAP
      rowBottom = Math.max(rowBottom, levelY + height)
    })

    maxBottom = Math.max(maxBottom, rowBottom)
  })

  return {
    positions,
    bottomY: maxBottom,
  }
}

const createAutoLayout = ({ nodes, edges, entryNodeId }) => {
  const nodeMap = new Map(nodes.map(node => [node.id, node]))
  const forwardAdjacency = new Map()
  const reverseAdjacency = new Map()
  const undirectedAdjacency = new Map()

  nodes.forEach((node) => {
    forwardAdjacency.set(node.id, new Set())
    reverseAdjacency.set(node.id, new Set())
    undirectedAdjacency.set(node.id, new Set())
  })

  edges.forEach((edge) => {
    if (!nodeMap.has(edge.source) || !nodeMap.has(edge.target)) return
    forwardAdjacency.get(edge.source)?.add(edge.target)
    reverseAdjacency.get(edge.target)?.add(edge.source)
    undirectedAdjacency.get(edge.source)?.add(edge.target)
    undirectedAdjacency.get(edge.target)?.add(edge.source)
  })

  const positions = []
  const laidOut = new Set()
  let currentY = 0

  const layoutComponent = (seedId) => {
    if (!seedId || laidOut.has(seedId) || !nodeMap.has(seedId)) return

    const componentIds = []
    const stack = [seedId]
    laidOut.add(seedId)

    while (stack.length) {
      const nodeId = stack.pop()
      componentIds.push(nodeId)
      ;[...(undirectedAdjacency.get(nodeId) || [])]
        .sort((a, b) => (nodeMap.get(a)?.position?.y || 0) - (nodeMap.get(b)?.position?.y || 0))
        .forEach((nextId) => {
          if (laidOut.has(nextId)) return
          laidOut.add(nextId)
          stack.push(nextId)
        })
    }

    const allowedIds = new Set(componentIds)
    const candidateRoots = componentIds.filter((nodeId) => {
      const parents = [...(reverseAdjacency.get(nodeId) || [])].filter(parentId => allowedIds.has(parentId))
      return parents.length === 0
    })
    const startIds = candidateRoots.length
      ? candidateRoots.sort((a, b) => (nodeMap.get(a)?.position?.x || 0) - (nodeMap.get(b)?.position?.x || 0))
      : [seedId]

    const layout = buildComponentLayout({
      startIds,
      nodeMap,
      forwardAdjacency,
      incomingAdjacency: reverseAdjacency,
      allowedIds: componentIds,
      startY: currentY,
    })

    positions.push(...layout.positions)
    currentY = layout.bottomY + COMPONENT_GAP
  }

  layoutComponent(entryNodeId)

  nodes
    .map(node => node.id)
    .filter(nodeId => !laidOut.has(nodeId))
    .sort((a, b) => {
      const aNode = nodeMap.get(a)
      const bNode = nodeMap.get(b)
      return (aNode?.position?.y || 0) - (bNode?.position?.y || 0) || (aNode?.position?.x || 0) - (bNode?.position?.x || 0)
    })
    .forEach(layoutComponent)

  return positions
}

const GraphEditorInner = () => {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef(null)
  const { screenToFlowPosition, fitView } = useReactFlow()

  const {
    agent, nodes, edges, isDirty,
    loadGraph, onNodesChange, onEdgesChange,
    addNode, addEdge: storeAddEdge, selectNode, selectEdge, clearSelection,
    setAgent, setNodePositions, layoutUndoSnapshot, setLayoutUndoSnapshot, clearLayoutUndoSnapshot,
  } = useGraphStore()

  const [loading, setLoading] = useState(true)
  const [showSchemaEditor, setShowSchemaEditor] = useState(false)
  const [showRunModal, setShowRunModal] = useState(false)
  const [showNodePalette, setShowNodePalette] = useState(true)
  const [showConfigPanel, setShowConfigPanel] = useState(true)
  const [configPanelWidth, setConfigPanelWidth] = useState(320)
  const [isResizingPanel, setIsResizingPanel] = useState(false)
  const [isRearranging, setIsRearranging] = useState(false)
  const [pendingNodeCreation, setPendingNodeCreation] = useState(null)
  const [pendingNodeName, setPendingNodeName] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getAgent(agentId)
        loadGraph(data)
      } catch (e) {
        toast.error('Failed to load agent')
        navigate('/')
      }
      setLoading(false)
    }
    load()
  }, [agentId])

  // Save node positions on drag stop
  const onNodeDragStop = useCallback(async (_, node) => {
    const nodeData = node.data
    if (nodeData?.id) {
      try {
        await updateNode(nodeData.id, { position_x: node.position.x, position_y: node.position.y })
      } catch (e) { /* silent */ }
    }
  }, [])

  // Handle dropping new nodes from palette
  const createCanvasNode = useCallback(async ({ nodeDefinition, position, nodeName }) => {
    const nodeType = nodeDefinition?.type
    const nodeSubtype = nodeDefinition?.subtype
    if (!nodeType || !nodeSubtype) return false

    const isLLM = nodeType === 'llm_call'
    const isCommunication = nodeType === 'communication'
    const defaultConfig = {
      ...(nodeDefinition?.default_config || {}),
      function_type: (!isLLM && !isCommunication) ? nodeSubtype : undefined,
      communication_type: isCommunication ? nodeSubtype : undefined,
    }

    try {
      const created = await createNode(agentId, {
        name: nodeName,
        type: nodeType,
        subtype: nodeSubtype,
        config: defaultConfig,
        position_x: position.x,
        position_y: position.y,
      })

      addNode({
        id: String(created.id),
        type: isLLM ? 'llmNode' : (isCommunication ? 'communicationNode' : 'functionalNode'),
        position,
        data: { ...created, label: nodeName },
      })
      syncNodeCounter(nodeName)
      return true
    } catch (e) {
      toast.error('Failed to create node')
      return false
    }
  }, [agentId, addNode])

  const onDrop = useCallback((event) => {
    event.preventDefault()
    const rawNodeDefinition = event.dataTransfer.getData('application/reactflow')
    if (!rawNodeDefinition) return

    let nodeDefinition
    try {
      nodeDefinition = JSON.parse(rawNodeDefinition)
    } catch {
      const isLegacyLLM = rawNodeDefinition === 'llm_call'
      nodeDefinition = {
        type: isLegacyLLM ? 'llm_call' : 'functional',
        subtype: isLegacyLLM ? 'chat' : rawNodeDefinition,
      }
    }

    const nodeType = nodeDefinition?.type
    const nodeSubtype = nodeDefinition?.subtype
    if (!nodeType || !nodeSubtype) return

    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const suggestedNodeName = getSuggestedNodeName(nodes)

    setPendingNodeCreation({
      nodeDefinition,
      position,
      nodeType,
      nodeSubtype,
    })
    setPendingNodeName(suggestedNodeName)
  }, [nodes, screenToFlowPosition])

  const closePendingNodeCreation = useCallback(() => {
    setPendingNodeCreation(null)
    setPendingNodeName('')
  }, [])

  const confirmPendingNodeCreation = useCallback(async () => {
    if (!pendingNodeCreation) return

    const trimmedNodeName = pendingNodeName.trim()
    if (!trimmedNodeName) {
      toast.error('Node name is required')
      return
    }

    const hasDuplicateName = nodes.some(
      node => String(node.data?.name || '').trim().toLowerCase() === trimmedNodeName.toLowerCase()
    )
    if (hasDuplicateName) {
      toast.error('A node with this name already exists')
      return
    }

    const created = await createCanvasNode({
      nodeDefinition: pendingNodeCreation.nodeDefinition,
      position: pendingNodeCreation.position,
      nodeName: trimmedNodeName,
    })
    if (created) closePendingNodeCreation()
  }, [closePendingNodeCreation, createCanvasNode, nodes, pendingNodeCreation, pendingNodeName])

  const onDragOver = useCallback((event) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Handle connecting nodes
  const onConnect = useCallback(async (params) => {
    try {
      const created = await createEdge(agentId, {
        source_node_id: Number(params.source),
        target_node_id: Number(params.target),
        edge_type: 'direct',
      })

      const newEdge = {
        ...params,
        id: String(created.id),
        type: 'default',
        data: created,
      }
      storeAddEdge(newEdge)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create edge')
    }
  }, [agentId, storeAddEdge])

  const onNodeClick = useCallback((_, node) => {
    setShowConfigPanel(true)
    selectNode(node)
  }, [selectNode])
  const onEdgeClick = useCallback((_, edge) => {
    setShowConfigPanel(true)
    selectEdge(edge)
  }, [selectEdge])
  const onPaneClick = useCallback(() => clearSelection(), [clearSelection])

  const startPanelResize = useCallback((event) => {
    event.preventDefault()
    setIsResizingPanel(true)
  }, [])

  useEffect(() => {
    if (!isResizingPanel) return

    const minWidth = 280
    const maxWidth = 620

    const onMove = (event) => {
      const nextWidth = Math.min(maxWidth, Math.max(minWidth, window.innerWidth - event.clientX))
      setConfigPanelWidth(nextWidth)
    }

    const onUp = () => setIsResizingPanel(false)

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)

    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [isResizingPanel])

  const persistNodePositions = useCallback(async (positions) => {
    const updates = positions.map(({ id, position }) => {
      const node = nodes.find(currentNode => currentNode.id === id)
      if (!node?.data?.id) return Promise.resolve()
      return updateNode(node.data.id, {
        position_x: position.x,
        position_y: position.y,
      })
    })

    const results = await Promise.allSettled(updates)
    return results.every(result => result.status === 'fulfilled')
  }, [nodes])

  const handleRearrangeFromEntry = useCallback(async () => {
    if (!agent?.entry_node || !nodes.length || isRearranging) return

    const entryNode = nodes.find(node => node.data?.name === agent.entry_node)
    if (!entryNode) {
      toast.error('Entry node not found in the current graph')
      return
    }

    const nextPositions = createAutoLayout({
      nodes,
      edges,
      entryNodeId: entryNode.id,
    })

    if (!nextPositions.length) return

    const previousPositions = nodes.map(node => ({
      id: node.id,
      position: { ...node.position },
    }))

    setIsRearranging(true)
    setNodePositions(nextPositions)
    setLayoutUndoSnapshot(previousPositions)

    const persisted = await persistNodePositions(nextPositions)
    setIsRearranging(false)

    if (!persisted) {
      toast.error('Graph rearranged, but some node positions failed to save')
    } else {
      toast.success('Graph rearranged from entry node')
    }

    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 400 })
    })
  }, [agent?.entry_node, edges, fitView, isRearranging, nodes, persistNodePositions, setLayoutUndoSnapshot, setNodePositions])

  const handleUndoRearrange = useCallback(async () => {
    if (!layoutUndoSnapshot?.length || isRearranging) return

    setIsRearranging(true)
    setNodePositions(layoutUndoSnapshot)
    const persisted = await persistNodePositions(layoutUndoSnapshot)
    setIsRearranging(false)

    if (!persisted) {
      toast.error('Previous layout restored, but some node positions failed to save')
      return
    }

    clearLayoutUndoSnapshot()
    toast.success('Previous layout restored')
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 300 })
    })
  }, [clearLayoutUndoSnapshot, fitView, isRearranging, layoutUndoSnapshot, persistNodePositions, setNodePositions])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading graph...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      <TopBar
        agent={agent}
        isDirty={isDirty}
        onSchemaEdit={() => setShowSchemaEditor(true)}
        onRun={() => setShowRunModal(true)}
        onRearrangeGraph={handleRearrangeFromEntry}
        onUndoLayout={handleUndoRearrange}
        canUndoLayout={Boolean(layoutUndoSnapshot?.length)}
        isRearranging={isRearranging}
      />

      <div className="flex flex-1 overflow-hidden">
        {showNodePalette && (
          <NodePalette onClose={() => setShowNodePalette(false)} />
        )}

        <div className="relative flex-1" ref={reactFlowWrapper}>
          {!showNodePalette && (
            <button
              onClick={() => setShowNodePalette(true)}
              className="absolute left-4 top-4 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: 'var(--surface)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
            >
              <PanelLeftOpen size={13} />
              Palette
            </button>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeDragStop={onNodeDragStop}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode="Delete"
          >
            <Background color="#1e293b" gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeColor={n => n.type === 'llmNode' ? '#7c3aed' : '#0ea5e9'}
              maskColor="rgba(10,14,26,0.8)"
            />
          </ReactFlow>
        </div>

        {showConfigPanel && (
          <div
            onMouseDown={startPanelResize}
            className="w-1 cursor-col-resize transition-colors"
            style={{ background: isResizingPanel ? 'rgba(99,102,241,0.45)' : 'transparent' }}
          />
        )}

        {showConfigPanel && (
          <ConfigPanel
            panelWidth={configPanelWidth}
            onClosePanel={() => setShowConfigPanel(false)}
          />
        )}
      </div>

      {showSchemaEditor && (
        <StateSchemaEditor
          agent={agent}
          onClose={() => setShowSchemaEditor(false)}
          onUpdate={(updated) => setAgent(updated)}
        />
      )}
      {showRunModal && agent && (
        <RunModal agent={agent} onClose={() => setShowRunModal(false)} />
      )}
      {pendingNodeCreation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              confirmPendingNodeCreation()
            }}
            className="w-[420px] max-w-[92vw] rounded-2xl"
            style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}
          >
            <div className="px-6 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-base font-semibold text-white">Name New Node</h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                Enter the node name before adding it to the canvas.
              </p>
            </div>

            <div className="px-6 py-5">
              <label className="block text-xs font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
                Node Name
              </label>
              <input
                autoFocus
                value={pendingNodeName}
                onChange={(event) => setPendingNodeName(event.target.value)}
                placeholder="node_name"
                className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
              />
            </div>

            <div className="flex justify-end gap-3 px-6 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
              <button
                type="button"
                onClick={closePendingNodeCreation}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ color: 'var(--text-muted)' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                Add Node
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

export const GraphEditor = () => (
  <ReactFlowProvider>
    <GraphEditorInner />
  </ReactFlowProvider>
)
