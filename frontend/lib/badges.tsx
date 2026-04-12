import { Trophy, XCircle, Clock } from "lucide-react";

export function getStatusBadge(isWin: boolean | null | undefined) {
  if (isWin === true) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
        <Trophy className="h-3 w-3" />
        Won
      </span>
    );
  }
  if (isWin === false) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
        <XCircle className="h-3 w-3" />
        Lost
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-slate-600/50 text-slate-300">
      <Clock className="h-3 w-3" />
      Pending
    </span>
  );
}
