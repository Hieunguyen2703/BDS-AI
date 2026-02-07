"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const COLORS = [
  "#3b82f6", // blue
  "#10b981", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
];

interface DistrictChartProps {
  data: {
    district: string;
    count: number;
    avg_price_per_m2?: number | null;
  }[];
}

export function DistrictChart({ data }: DistrictChartProps) {
  const chartData = data.slice(0, 10).map((d) => ({
    name: d.district,
    "Số tin": d.count,
    "Giá TB (tr/m²)": d.avg_price_per_m2
      ? Math.round(d.avg_price_per_m2 / 1_000_000)
      : 0,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Thống kê theo quận/huyện</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="name" type="category" width={100} fontSize={12} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Số tin" fill="#3b82f6" />
            <Bar dataKey="Giá TB (tr/m²)" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

interface PlatformChartProps {
  data: {
    platform: string;
    count: number;
    percentage: number;
  }[];
}

export function PlatformChart({ data }: PlatformChartProps) {
  const chartData = data.map((d, i) => ({
    name: d.platform,
    value: d.count,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nguồn dữ liệu</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) =>
                `${name} (${(percent * 100).toFixed(0)}%)`
              }
              outerRadius={100}
              fill="#8884d8"
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

interface PriceTrendChartProps {
  data: {
    date: string;
    avg_price_per_m2: number;
    count: number;
  }[];
}

export function PriceTrendChart({ data }: PriceTrendChartProps) {
  const chartData = data.map((d) => ({
    date: d.date,
    "Giá TB (tr/m²)": d.avg_price_per_m2
      ? Math.round(d.avg_price_per_m2 / 1_000_000)
      : 0,
    "Số tin": d.count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Xu hướng giá theo thời gian</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={12} />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="Giá TB (tr/m²)"
              stroke="#3b82f6"
              strokeWidth={2}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="Số tin"
              stroke="#10b981"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

interface StatsCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export function StatsCard({
  title,
  value,
  description,
  icon,
  trend,
}: StatsCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        {trend && (
          <p
            className={`text-xs ${
              trend.isPositive ? "text-green-600" : "text-red-600"
            }`}
          >
            {trend.isPositive ? "+" : "-"}
            {Math.abs(trend.value)}% so với tuần trước
          </p>
        )}
      </CardContent>
    </Card>
  );
}
