import { BaseEdge, EdgeLabelRenderer, getBezierPath } from 'reactflow'
import { useGraphStore } from '../../hooks/useGraphStore'

export const ConditionalEdge = ({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, label, markerEnd, style
}) => {
  const { selectEdge, selectedEdge } = useGraphStore()
  const isSelected = selectedEdge?.id === id
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition })

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: isSelected ? '#6366f1' : '#f59e0b',
          strokeWidth: 2,
          strokeDasharray: '6 3',
        }}
        onClick={() => selectEdge({ id, data })}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="absolute px-2 py-0.5 rounded text-xs font-mono cursor-pointer"
            onClick={() => selectEdge({ id, data })}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
              background: '#f59e0b22',
              border: '1px solid #f59e0b55',
              color: '#fbbf24',
              fontSize: '10px',
              fontFamily: 'monospace',
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export const edgeTypes = {
  conditionalEdge: ConditionalEdge,
}
