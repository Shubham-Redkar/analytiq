"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { AnalyticalResultColumn } from "../../lib/analysis-types";
import { recommendChart, type ChartRecommendation } from "../../lib/chart-recommender";
import { formatDisplayHeader } from "../../lib/suggested-questions";

interface ChartContainerProps {
  columns: AnalyticalResultColumn[];
  rows: (string | number | boolean | null)[][];
  returnedRowCount: number;
  truncated?: boolean;
}

/** Format a numeric value for display on the chart axis / tooltip. */
function formatMetricValue(value: number, isProportion: boolean): string {
  if (isProportion) {
    return `${(value * 100).toFixed(1)}%`;
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function ChartContainer({
  columns,
  rows,
  returnedRowCount,
  truncated = false,
}: ChartContainerProps) {
  const rec: ChartRecommendation = useMemo(() => {
    return recommendChart(columns, rows, returnedRowCount, truncated);
  }, [columns, rows, returnedRowCount, truncated]);

  const chartData = useMemo(() => {
    if (!rec.isEligible || rec.type === "table" || rec.type === "metric") {
      return [];
    }

    const dimIdx = rec.dimensionColumn
      ? columns.findIndex((c) => c.name === rec.dimensionColumn)
      : -1;
    const metricIdx = rec.metricColumn ? columns.findIndex((c) => c.name === rec.metricColumn) : -1;

    // Limit visualization complexity to top 50 rows
    const boundedRows = rows.slice(0, 50);

    return boundedRows.map((r) => {
      const point: Record<string, unknown> = {};
      if (dimIdx >= 0) {
        point[rec.dimensionColumn!] = String(r[dimIdx] ?? "NULL");
      }
      if (metricIdx >= 0) {
        point[rec.metricColumn!] =
          typeof r[metricIdx] === "number" ? r[metricIdx] : Number(r[metricIdx]) || 0;
      }
      return point;
    });
  }, [rec, columns, rows]);

  if (!rec.isEligible) {
    // Show a message rather than nothing, so the user understands why no chart is shown
    return (
      <div className="flex flex-col items-center justify-center py-8 text-sm text-muted-foreground gap-2">
        <span className="text-2xl">📊</span>
        <span>No chart available — viewing data in table form below.</span>
      </div>
    );
  }

  // 1. Single scalar metric display
  if (rec.type === "metric") {
    const val = rows[0]?.[0];
    return (
      <div className="p-6 border rounded-xl bg-card text-center my-3 max-w-sm mx-auto shadow-xs">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider block mb-1">
          {formatDisplayHeader(rec.title)}
        </span>
        <span className="text-3xl font-bold tracking-tight text-foreground font-mono">
          {typeof val === "number"
            ? val.toLocaleString(undefined, { maximumFractionDigits: 4 })
            : String(val)}
        </span>
      </div>
    );
  }

  const isProportion = rec.metricIsProportion ?? false;
  const dimLabel = rec.dimensionColumn ? formatDisplayHeader(rec.dimensionColumn) : "";
  const metricLabel = rec.metricColumn
    ? isProportion
      ? "Survival rate (%)"
      : formatDisplayHeader(rec.metricColumn)
    : "";
  const chartTitle = `${metricLabel} by ${dimLabel}`;

  return (
    <div className="border rounded-xl p-4 bg-card my-3 space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
        <span className="font-semibold text-foreground text-sm">{chartTitle}</span>
        {truncated && <span className="text-amber-500 font-medium">Top subset displayed</span>}
      </div>

      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          {rec.type === "line" ? (
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 20, left: isProportion ? 20 : 0, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey={rec.dimensionColumn}
                tick={{ fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={isProportion ? (v: number) => `${(v * 100).toFixed(0)}%` : undefined}
                domain={isProportion ? [0, 1] : ["auto", "auto"]}
              />
              <Tooltip
                formatter={(value) => [
                  formatMetricValue(
                    typeof value === "number" ? value : Number(value) || 0,
                    isProportion
                  ),
                  metricLabel,
                ]}
                contentStyle={{
                  backgroundColor: "var(--color-card, #1e293b)",
                  borderColor: "var(--color-border, #334155)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Line
                type="monotone"
                dataKey={rec.metricColumn}
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          ) : (
            <BarChart
              data={chartData}
              layout={rec.type === "horizontal-bar" ? "vertical" : "horizontal"}
              margin={{
                top: 10,
                right: 20,
                left: rec.type === "horizontal-bar" ? 40 : isProportion ? 20 : 0,
                bottom: 20,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              {rec.type === "horizontal-bar" ? (
                <>
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    tickFormatter={
                      isProportion ? (v: number) => `${(v * 100).toFixed(0)}%` : undefined
                    }
                    domain={isProportion ? [0, 1] : ["auto", "auto"]}
                  />
                  <YAxis dataKey={rec.dimensionColumn} type="category" tick={{ fontSize: 11 }} />
                </>
              ) : (
                <>
                  <XAxis dataKey={rec.dimensionColumn} tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={
                      isProportion ? (v: number) => `${(v * 100).toFixed(0)}%` : undefined
                    }
                    domain={isProportion ? [0, 1] : ["auto", "auto"]}
                  />
                </>
              )}
              <Tooltip
                formatter={(value) => [
                  formatMetricValue(
                    typeof value === "number" ? value : Number(value) || 0,
                    isProportion
                  ),
                  metricLabel,
                ]}
                contentStyle={{
                  backgroundColor: "var(--color-card, #1e293b)",
                  borderColor: "var(--color-border, #334155)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey={rec.metricColumn} fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
