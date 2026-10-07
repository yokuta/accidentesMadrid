import {handle,results} from "@/lib/server";
export const GET=(req:Request)=>handle(()=>results(req));
