import { create } from 'zustand'
import { applyNodeChanges, applyEdgeChanges } from 'reactflow'

const normalizeAgent = (agent) => {
  if (!agent) return agent
  const rawExitNodes = Array.isArray(agent.exit_nodes)
    ? agent.exit_nodes.filter(name => typeof name === 'string' && name.trim())
    : (agent.exit_node ? [agent.exit_node] : [])
  const exitNodes = [...new Set(rawExitNodes)]

  return {
    ...agent,
    exit_nodes: exitNodes,
    exit_node: exitNodes[0] || null,
  }
}

export const useGraphStore = create((set, get) => ({
  agent: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedEdge: null,
  isDirty: false,
  layoutUndoSnapshot: null,
  latestRun: null,

  setAgent: (agent) => set({ agent: normalizeAgent(agent) }),

  loadGraph: (agent) => {
    const normalizedAgent = normalizeAgent(agent)
    const rfNodes = (normalizedAgent.nodes || []).map(n => ({
      id: String(n.id),
      type: n.type === 'llm_call' ? 'llmNode' : 'functionalNode',
      position: { x: n.position_x || 0, y: n.position_y || 0 },
      data: { ...n, label: n.name },
    }))

    const rfEdges = (normalizedAgent.edges || []).map(e => ({
      id: String(e.id),
      source: String(e.source_node_id),
      target: String(e.target_node_id),
      type: e.edge_type === 'conditional' ? 'conditionalEdge' : 'default',
      label: e.label || '',
      animated: e.edge_type === 'conditional',
      data: { ...e },
    }))

    set({
      agent: normalizedAgent,
      nodes: rfNodes,
      edges: rfEdges,
      isDirty: false,
      layoutUndoSnapshot: null,
      latestRun: null,
      selectedNode: null,
      selectedEdge: null,
    })
  },

  onNodesChange: (changes) => {
    set(state => ({
      nodes: applyNodeChanges(changes, state.nodes),
      isDirty: true,
    }))
  },

  onEdgesChange: (changes) => {
    set(state => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    }))
  },

  addNode: (node) => {
    set(state => ({
      nodes: [...state.nodes, node],
      isDirty: true,
    }))
  },

  updateNodeData: (nodeId, data) => {
    set(state => ({
      nodes: state.nodes.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n),
      isDirty: true,
    }))
  },

  removeNode: (nodeId) => {
    set(state => {
      const removedNode = state.nodes.find(n => n.id === nodeId)
      const removedName = removedNode?.data?.name
      const exitNodes = (state.agent?.exit_nodes || []).filter(name => name !== removedName)

      return {
        agent: state.agent ? {
          ...state.agent,
          entry_node: state.agent.entry_node === removedName ? null : state.agent.entry_node,
          exit_nodes: exitNodes,
          exit_node: exitNodes[0] || null,
        } : state.agent,
        nodes: state.nodes.filter(n => n.id !== nodeId),
        edges: state.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
        isDirty: true,
      }
    })
  },

  addEdge: (edge) => {
    set(state => ({
      edges: [...state.edges, edge],
      isDirty: true,
    }))
  },

  updateEdgeData: (edgeId, data) => {
    set(state => {
      const edges = state.edges.map(edge => (
        edge.id === edgeId
          ? {
              ...edge,
              ...data,
              data: { ...edge.data, ...data },
            }
          : edge
      ))
      const selectedEdge = state.selectedEdge
        ? edges.find(edge => edge.id === state.selectedEdge.id) || state.selectedEdge
        : null

      return {
        edges,
        selectedEdge,
        isDirty: true,
      }
    })
  },

  setNodePositions: (positions) => {
    set(state => {
      const positionMap = new Map(positions.map(({ id, position }) => [String(id), position]))
      const nodes = state.nodes.map((node) => {
        const nextPosition = positionMap.get(node.id)
        return nextPosition ? { ...node, position: nextPosition } : node
      })
      const selectedNode = state.selectedNode
        ? nodes.find(node => node.id === state.selectedNode.id) || state.selectedNode
        : null

      return {
        nodes,
        selectedNode,
        isDirty: true,
      }
    })
  },

  removeEdge: (edgeId) => {
    set(state => ({
      edges: state.edges.filter(e => e.id !== edgeId),
      isDirty: true,
    }))
  },

  selectNode: (node) => set({ selectedNode: node, selectedEdge: null }),
  selectEdge: (edge) => set({ selectedEdge: edge, selectedNode: null }),
  clearSelection: () => set({ selectedNode: null, selectedEdge: null }),
  setLayoutUndoSnapshot: (snapshot) => set({ layoutUndoSnapshot: snapshot }),
  clearLayoutUndoSnapshot: () => set({ layoutUndoSnapshot: null }),
  setLatestRun: (latestRun) => set({ latestRun }),
  markClean: () => set({ isDirty: false }),
}))
