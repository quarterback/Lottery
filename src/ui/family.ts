// The family of sibling tools — cross-navigation links. Lottery Lab is part of
// the Cap Buffet universe (capbuffet.com); update the `url`s here if a tool moves.

export interface FamilyTool {
  id: string
  name: string
  blurb: string
  url: string
  /** The tool currently being viewed (shown as "you're here", not a link). */
  current?: boolean
}

export const FAMILY_TOOLS: FamilyTool[] = [
  { id: 'cap-buffet', name: 'Cap Buffet', blurb: 'Salary cap imagineering', url: 'https://capbuffet.com/' },
  { id: 'lottery-lab', name: 'Lottery Lab', blurb: 'Draft-lottery simulator', url: 'https://lottery.capbuffet.com/', current: true },
  // Expansion Draft — add the URL when it's live (ideally a capbuffet.com subdomain):
  // { id: 'expansion-draft', name: 'Expansion Draft', blurb: 'Build an expansion roster', url: '' },
]
