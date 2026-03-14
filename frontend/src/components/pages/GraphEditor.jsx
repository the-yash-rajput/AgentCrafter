import { useEffect, useCallback, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactFlow, {
  Background, Controls, MiniMap, addEdge, useReactFlow, ReactFlowProvider,
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

const GraphEditorInner = () => {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef(null)
  const { screenToFlowPosition } = useReactFlow()

  const {
    agent, nodes, edges, isDirty,
    loadGraph, onNodesChange, onEdgesChange,
    addNode, addEdge: storeAddEdge, selectNode, selectEdge, clearSelection,
    setAgent,
  } = useGraphStore()

  const [loading, setLoading] = useState(true)
  const [showSchemaEditor, setShowSchemaEditor] = useState(false)
  const [showRunModal, setShowRunModal] = useState(false)

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
  const onDrop = useCallback(async (event) => {
    event.preventDefault()
    const nodeType = event.dataTransfer.getData('application/reactflow')
    if (!nodeType) return

    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const nodeName = `node_${nodeCounter++}`

    const isLLM = nodeType === 'llm_call'
    const defaultConfig = isLLM
      ? {
          node_type: 'llm_call',
          provider: 'azure_openai',
          model: 'ai-agent-4o',
          api_key_env_var: 'AZURE_OPENAI_API_KEY',
          temperature: 0.7,
          max_tokens: 1000,
          output_key: 'llm_response'
        }
      : { node_type: 'functional', function_type: nodeType === 'llm_call' ? 'python_inline' : nodeType, python_inline: { code: 'def run(state):\n    return state' } }

    try {
      const created = await createNode(agentId, {
        name: nodeName,
        type: isLLM ? 'llm_call' : 'functional',
        config: defaultConfig,
        position_x: position.x,
        position_y: position.y,
      })

      addNode({
        id: nodeName,
        type: isLLM ? 'llmNode' : 'functionalNode',
        position,
        data: { ...created, label: nodeName },
      })
    } catch (e) {
      toast.error('Failed to create node')
    }
  }, [agentId, screenToFlowPosition, addNode])

  const onDragOver = useCallback((event) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Handle connecting nodes
  const onConnect = useCallback(async (params) => {
    try {
      const created = await createEdge(agentId, {
        source_node_id: params.source,
        target_node_id: params.target,
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
      toast.error('Failed to create edge')
    }
  }, [agentId, storeAddEdge])

  const onNodeClick = useCallback((_, node) => selectNode(node), [selectNode])
  const onEdgeClick = useCallback((_, edge) => selectEdge(edge), [selectEdge])
  const onPaneClick = useCallback(() => clearSelection(), [clearSelection])

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
      />

      <div className="flex flex-1 overflow-hidden">
        <NodePalette />

        <div className="flex-1" ref={reactFlowWrapper}>
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

        <ConfigPanel />
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
    </div>
  )
}

export const GraphEditor = () => (
  <ReactFlowProvider>
    <GraphEditorInner />
  </ReactFlowProvider>
)
