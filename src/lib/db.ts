export type ID = string
export interface Pattern { id: ID; name: string; description: string; kind: string; }
const apiBase = "http://localhost:8000"

export async function getPattern(id: ID) {
    const response = await fetch(`${apiBase}/patterns/${id}`)
    return await response.json()
}