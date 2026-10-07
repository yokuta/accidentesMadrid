import {handle,vote} from "@/lib/server";
export const POST=(req:Request)=>handle(()=>vote(req));
