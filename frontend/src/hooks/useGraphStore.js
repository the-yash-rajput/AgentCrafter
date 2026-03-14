import { create } from 'zustand'
import { applyNodeChanges, applyEdgeChanges } from 'reactflow'

export const useGraphStore = create((set, get) => ({
  agent: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedEdge: null,
  isDirty: false,

  setAgent: (agent) => set({ agent }),

  loadGraph: (agent) => {
    const rfNodes = (agent.nodes || []).map(n => ({
      id: n.name,
      type: n.type === 'llm_call' ? 'llmNode' : 'functionalNode',
      position: { x: n.position_x || 0, y: n.position_y || 0 },
      data: { ...n, label: n.name },
    }))

    const rfEdges = (agent.edges || []).map(e => ({
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      type: e.edge_type === 'conditional' ? 'conditionalEdge' : 'default',
      label: e.label || '',
      animated: e.edge_type === 'conditional',
      data: { ...e },
    }))

    set({ agent, nodes: rfNodes, edges: rfEdges, isDirty: false })
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
    set(state => ({
      nodes: state.nodes.filter(n => n.id !== nodeId),
      edges: state.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
      isDirty: true,
    }))
  },

  addEdge: (edge) => {
    set(state => ({
      edges: [...state.edges, edge],
      isDirty: true,
    }))
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
  markClean: () => set({ isDirty: false }),
}))
