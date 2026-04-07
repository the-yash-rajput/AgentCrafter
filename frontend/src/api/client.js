import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: `${BASE}/api` })

// Agents
export const getAgents = () => api.get('/agents').then(r => r.data)
export const getAgent = (id) => api.get(`/agents/${id}`).then(r => r.data)
export const createAgent = (data) => api.post('/agents', data).then(r => r.data)
export const updateAgent = (id, data) => api.put(`/agents/${id}`, data).then(r => r.data)
export const deleteAgent = (id) => api.delete(`/agents/${id}`).then(r => r.data)
export const duplicateAgent = (id) => api.post(`/agents/${id}/duplicate`).then(r => r.data)
export const exportAgent = (id) => api.get(`/agents/${id}/export`).then(r => r.data)
export const importAgent = (data) => api.post('/agents/import', data).then(r => r.data)
export const validateAgent = (id) => api.get(`/agents/${id}/validate`).then(r => r.data)

// Nodes
export const getNodeDefinitions = () => api.get('/node-definitions').then(r => r.data)
export const createNode = (agentId, data) => api.post(`/agents/${agentId}/nodes`, data).then(r => r.data)
export const updateNode = (nodeId, data) => api.put(`/nodes/${nodeId}`, data).then(r => r.data)
export const deleteNode = (nodeId) => api.delete(`/nodes/${nodeId}`).then(r => r.data)

// Edges
export const createEdge = (agentId, data) => api.post(`/agents/${agentId}/edges`, data).then(r => r.data)
export const updateEdge = (edgeId, data) => api.put(`/edges/${edgeId}`, data).then(r => r.data)
export const deleteEdge = (edgeId) => api.delete(`/edges/${edgeId}`).then(r => r.data)

// Runs
export const runAgent = (agentId, payload) => api.post(`/agents/${agentId}/run`, payload).then(r => r.data)
export const getRun = (runId) => api.get(`/runs/${runId}`).then(r => r.data)
export const getRuns = (agentId) => api.get(`/agents/${agentId}/runs`).then(r => r.data)

// Langfuse
export const getLangfusePrompts = () => api.get('/langfuse/prompts').then(r => r.data)
