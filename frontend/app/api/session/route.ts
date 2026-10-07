import {handle,json,startSession,getSession,sessionView} from "@/lib/server";
export const GET=(req:Request)=>handle(async()=>json(await sessionView(await getSession(req))));
export const POST=(req:Request)=>handle(()=>startSession(req));
