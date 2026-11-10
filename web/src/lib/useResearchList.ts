"use client";

import { useContext } from "react";

import { ResearchListContext, type ResearchListState } from "@/components/ResearchListProvider";

export function useResearchList(): ResearchListState {
  const state = useContext(ResearchListContext);
  if (!state) throw new Error("useResearchList must be used inside <ResearchListProvider>");
  return state;
}
