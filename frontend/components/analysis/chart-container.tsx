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

/** Truncate label with ellipsis for y-axis rendering without overlapping. */
function truncateLabel(str: string, maxLen: number = 24): string {
  if (!str) return "";
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 1) + "…";
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
        const rawDim = String(r[dimIdx] ?? "NULL");
        point[rec.dimensionColumn!] = rawDim;
        point[`${rec.dimensionColumn!}_display`] = truncateLabel(rawDim, 25);
      }
      if (metricIdx >= 0) {
        point[rec.metricColumn!] =
          typeof r[metricIdx] === "number" ? r[metricIdx] : Number(r[metricIdx]) || 0;
      }
      return point;
    });
  }, [rec, columns, rows]);

  if (!rec.isEligible) {
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
  const isHorizontal = rec.type === "horizontal-bar";
  const dimLabel = rec.dimensionColumn ? formatDisplayHeader(rec.dimensionColumn) : "";
  const metricLabel = rec.metricColumn ? formatDisplayHeader(rec.metricColumn) : "";
  const chartTitle = `${metricLabel} by ${dimLabel}`;

  // Dynamic height for horizontal bar charts to prevent overlapping bars
  const chartHeight = isHorizontal ? Math.max(260, chartData.length * 48 + 70) : 280;

  return (
    <div className="border rounded-xl p-4 bg-card my-3 space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
        <span className="font-semibold text-foreground text-sm">{chartTitle}</span>
        {truncated && <span className="text-amber-500 font-medium">Top subset displayed</span>}
      </div>

      <div className="w-full" style={{ height: `${chartHeight}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          {rec.type === "line" ? (
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 20, left: isProportion ? 20 : 0, bottom: 25 }}
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
                domain={isProportion ? [0, 1] : [0, "auto"]}
              />
              <Tooltip
                formatter={(value) => [
                  formatMetricValue(
                    typeof value === "number" ? value : Number(value) || 0,
                    isProportion
                  ),
                  metricLabel,
                ]}
                labelFormatter={(label) => String(label)}
                contentStyle={{
                  backgroundColor: "var(--color-card, #1e293b)",
                  borderColor: "var(--color-border, #334155)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--color-foreground, #f8fafc)",
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
              layout={isHorizontal ? "vertical" : "horizontal"}
              margin={{
                top: 10,
                right: 25,
                left: isHorizontal ? 20 : isProportion ? 20 : 10,
                bottom: 20,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              {isHorizontal ? (
                <>
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    tickFormatter={
                      isProportion
                        ? (v: number) => `${(v * 100).toFixed(0)}%`
                        : (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v))
                    }
                    domain={isProportion ? [0, 1] : [0, "auto"]}
                  />
                  <YAxis
                    dataKey={`${rec.dimensionColumn!}_display`}
                    type="category"
                    tick={{ fontSize: 11 }}
                    width={160}
                    interval={0}
                  />
                </>
              ) : (
                <>
                  <XAxis
                    dataKey={rec.dimensionColumn}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => truncateLabel(String(v), 16)}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={
                      isProportion ? (v: number) => `${(v * 100).toFixed(0)}%` : undefined
                    }
                    domain={isProportion ? [0, 1] : [0, "auto"]}
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
                labelFormatter={(_label, payload) => {
                  const original = payload?.[0]?.payload?.[rec.dimensionColumn!] ?? _label;
                  return `${dimLabel}: ${original}`;
                }}
                contentStyle={{
                  backgroundColor: "var(--color-card, #1e293b)",
                  borderColor: "var(--color-border, #334155)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--color-foreground, #f8fafc)",
                }}
              />
              <Bar
                dataKey={rec.metricColumn}
                fill="#3b82f6"
                radius={isHorizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
              />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
