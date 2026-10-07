// Vacío usa la API de la plataforma. VITE_API_BASE permite usar el backend portable.
export function apiUrl(path:string){const base=String((import.meta as any).env?.VITE_API_BASE||"").replace(/\/$/,"");return `${base}${path}`;}
