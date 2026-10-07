import {handle,exportData} from "@/lib/server";
export const GET=(req:Request)=>handle(()=>exportData(req));
