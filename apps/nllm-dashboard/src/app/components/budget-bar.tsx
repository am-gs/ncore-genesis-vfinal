'use client';

import { BudgetInfo } from '@/app/types';

export function BudgetBar({ budget }: { budget: BudgetInfo }) {
  const dailyPct = Math.min((budget.daily / budget.daily_limit) * 100, 100);
  const monthlyPct = Math.min((budget.monthly / budget.monthly_limit) * 100, 100);

  const getColor = (pct: number) => {
    if (pct < 50) return 'bg-ok';
    if (pct < 80) return 'bg-warn';
    return 'bg-bad';
  };

  return (
    <div className="space-y-3">
      <h4 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
        Budget
      </h4>

      {/* Daily */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px]">
          <span className="text-text-secondary">Today</span>
          <span className="text-text-tertiary">
            ${budget.daily.toFixed(2)} / ${budget.daily_limit.toFixed(2)}
          </span>
        </div>
        <div className="h-1.5 bg-bg-2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getColor(dailyPct)}`}
            style={{ width: `${dailyPct}%` }}
          />
        </div>
      </div>

      {/* Monthly */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px]">
          <span className="text-text-secondary">This month</span>
          <span className="text-text-tertiary">
            ${budget.monthly.toFixed(2)} / ${budget.monthly_limit.toFixed(2)}
          </span>
        </div>
        <div className="h-1.5 bg-bg-2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getColor(monthlyPct)}`}
            style={{ width: `${monthlyPct}%` }}
          />
        </div>
      </div>

      {/* Cache hit rate */}
      <div className="flex items-center justify-between text-[10px] text-text-tertiary pt-1">
        <span>Cache hits</span>
        <span className="text-accent">{(budget.cache_hit_rate * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
