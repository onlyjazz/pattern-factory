export interface ResultTable {
    id: string;
    sessionId: string;
    name: string;
    columns: string[];
    rows: any[][];
    createdAt: number;
    updatedAt: number;
    sourceHash?: string; // optional to dedupe by SQL/query
}