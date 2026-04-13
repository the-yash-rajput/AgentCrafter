import { BaseEdge, EdgeLabelRenderer, getBezierPath } from 'reactflow'
import { useGraphStore } from '../../hooks/useGraphStore'

const buildSelectedEdgePayload = ({ id, source, target, data, label, type, animated }) => ({
  id,
  source,
  target,
  data,
  label,
  type,
  animated,
})

const BezierSelectableEdge = ({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  label,
  markerEnd,
  style,
  pathOptions,
  interactionWidth,
  variant,
}) => {
  const { selectEdge, selectedEdge } = useGraphStore()
  const isSelected = selectedEdge?.id === id
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: pathOptions?.curvature,
  })
  const edgeType = variant === 'conditional' ? 'conditionalEdge' : 'directEdge'
  const handleSelect = () => {
    selectEdge(buildSelectedEdgePayload({
      id,
      source,
      target,
      data,
      label,
      type: edgeType,
      animated: variant === 'conditional',
    }))
  }
  const handleLabelClick = (event) => {
    event.stopPropagation()
    handleSelect()
  }
  const strokeColor = isSelected
    ? '#6366f1'
    : variant === 'conditional'
      ? '#f59e0b'
      : '#94a3b8'

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth}
        style={{
          ...style,
          stroke: strokeColor,
          strokeWidth: isSelected ? 3 : 2,
          strokeDasharray: variant === 'conditional' ? '6 3' : undefined,
          strokeLinecap: 'round',
        }}
        onClick={handleSelect}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="absolute px-2 py-0.5 rounded text-xs font-mono cursor-pointer"
            onClick={handleLabelClick}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
              background: variant === 'conditional' ? '#f59e0b22' : '#94a3b822',
              border: variant === 'conditional' ? '1px solid #f59e0b55' : '1px solid #94a3b855',
              color: variant === 'conditional' ? '#fbbf24' : '#cbd5e1',
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

export const DirectEdge = (props) => (
  <BezierSelectableEdge {...props} variant="direct" />
)

export const ConditionalEdge = (props) => (
  <BezierSelectableEdge {...props} variant="conditional" />
)

export const edgeTypes = {
  directEdge: DirectEdge,
  conditionalEdge: ConditionalEdge,
}
