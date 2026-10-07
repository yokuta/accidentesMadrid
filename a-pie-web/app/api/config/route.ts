import {handle,config} from "@/lib/server";
export const GET=()=>handle(()=>config());
