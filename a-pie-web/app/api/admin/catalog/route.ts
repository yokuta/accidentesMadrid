import {handle,uploadCatalog} from "@/lib/server";
export const POST=(req:Request)=>handle(()=>uploadCatalog(req));
