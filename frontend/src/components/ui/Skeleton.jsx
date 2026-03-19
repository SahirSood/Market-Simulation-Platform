/**
 * Generic loading pulse skeleton.
 * className: override width/height as needed.
 */
export default function Skeleton({ className = "h-4 w-24" }) {
  return (
    <div className={`animate-pulse bg-[#1E1E2E] rounded ${className}`} />
  );
}
