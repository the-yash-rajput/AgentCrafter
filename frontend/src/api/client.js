import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: `${BASE}/api` })

const findVersionByReference = (versions, versionRef) => {
  const normalizedRef = String(versionRef ?? '').trim()
  if (!normalizedRef) return null

  return (
    versions.find(version => String(version.version_number) === normalizedRef) ||
    versions.find(version => String(version.id) === normalizedRef) ||
    null
  )
}

// Agents
export const getAgents = () => api.get('/agents').then(r => r.data)
export const getAgent = (id, versionId) => api.get(`/agents/${id}`, {
  params: versionId ? { version_id: versionId } : undefined,
}).then(r => r.data)
export const createAgent = (data) => api.post('/agents', data).then(r => r.data)
export const updateAgent = (id, data) => api.put(`/agents/${id}`, data).then(r => r.data)
export const deleteAgent = (id) => api.delete(`/agents/${id}`).then(r => r.data)
export const duplicateAgent = (id) => api.post(`/agents/${id}/duplicate`).then(r => r.data)
export const exportAgent = (id) => api.get(`/agents/${id}/export`).then(r => r.data)
export const importAgent = (data) => api.post('/agents/import', data).then(r => r.data)
export const validateAgent = (id, versionId) => api.get(`/agents/${id}/validate`, {
  params: versionId ? { version_id: versionId } : undefined,
}).then(r => r.data)
export const getAgentVersions = (agentId) => api.get(`/agents/${agentId}/versions`).then(r => r.data)
export const resolveAgentVersion = async (agentId, versionRef) => {
  const versions = await getAgentVersions(agentId)
  const version = findVersionByReference(versions, versionRef)
  if (!version) {
    throw new Error('Agent version not found')
  }
  return version
}
export const getAgentByVersionRef = async (agentId, versionRef) => {
  const version = await resolveAgentVersion(agentId, versionRef)
  return getAgent(agentId, version.id)
}
export const getAgentVersion = (agentId, versionId) => api.get(`/agents/${agentId}/versions/${versionId}`).then(r => r.data)
export const createAgentVersion = (agentId, baseVersionId) => api.post(`/agents/${agentId}/versions`, {
  base_version_id: baseVersionId,
}).then(r => r.data)
export const updateAgentVersion = (agentId, versionId, data) => api.put(`/agents/${agentId}/versions/${versionId}`, data).then(r => r.data)

// Nodes
export const getNodeDefinitions = () => api.get('/node-definitions').then(r => r.data)
export const createNode = (agentId, data, versionId) => (
  versionId
    ? api.post(`/agents/${agentId}/versions/${versionId}/nodes`, data)
    : api.post(`/agents/${agentId}/nodes`, data)
).then(r => r.data)
export const updateNode = (nodeId, data) => api.put(`/nodes/${nodeId}`, data).then(r => r.data)
export const deleteNode = (nodeId) => api.delete(`/nodes/${nodeId}`).then(r => r.data)

// Edges
export const createEdge = (agentId, data, versionId) => (
  versionId
    ? api.post(`/agents/${agentId}/versions/${versionId}/edges`, data)
    : api.post(`/agents/${agentId}/edges`, data)
).then(r => r.data)
export const updateEdge = (edgeId, data) => api.put(`/edges/${edgeId}`, data).then(r => r.data)
export const deleteEdge = (edgeId) => api.delete(`/edges/${edgeId}`).then(r => r.data)

// Runs
export const runAgent = (agentId, payload) => api.post(`/agents/${agentId}/run`, payload).then(r => r.data)
export const getRun = (runId) => api.get(`/runs/${runId}`).then(r => r.data)
export const getRuns = (agentId) => api.get(`/agents/${agentId}/runs`).then(r => r.data)
export const createAgentSession = (agentId, versionId, payload = {}) => (
  api.post(`/agents/${agentId}/versions/${versionId}/sessions`, payload)
).then(r => r.data)
export const getAgentSession = (agentId, versionId, sessionId) => (
  api.get(`/agents/${agentId}/versions/${versionId}/sessions/${sessionId}`)
).then(r => r.data)
export const runAgentSession = (agentId, versionId, sessionId, payload) => (
  api.post(`/agents/${agentId}/versions/${versionId}/sessions/${sessionId}/runs`, payload)
).then(r => r.data)

// Langfuse
export const getLangfusePrompts = () => api.get('/langfuse/prompts').then(r => r.data)
