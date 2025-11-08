import MarkdownIt from 'markdown-it'

/**
 * Markdown renderer configured for clinical documentation
 *
 * Security: HTML disabled to prevent XSS
 * Typography: Smart quotes, em-dashes for professional appearance
 * Breaks: Convert \n to <br> for better clinical note formatting
 */
const md = new MarkdownIt({
  html: false, // CRITICAL: Disable HTML for security (prevent XSS)
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Smart quotes, em-dashes
  breaks: true, // Convert \n to <br> (clinical notes often have line breaks)
})

// Customize strong (bold) rendering with contextual styling
// Section headers (ending with colon) get larger, block-level styling
// Regular bold (dates, emphasis) stays inline and smaller
md.renderer.rules.strong_open = (tokens, idx) => {
  const nextToken = tokens[idx + 1]
  const content = nextToken?.content || ''

  // Section headers end with colon (e.g., "Chief Complaint:")
  if (content.trim().endsWith(':')) {
    return '<strong class="block font-semibold text-base text-slate-900 mt-4 mb-1.5 first:mt-0 border-l-3 border-emerald-500/20 pl-3 -ml-3">'
  }

  // Regular bold (dates, emphasis) - inline, medium weight
  return '<strong class="font-medium text-slate-800">'
}

// Customize heading rendering for clinical context
md.renderer.rules.heading_open = (tokens, idx) => {
  const level = tokens[idx].tag
  const classes: Record<string, string> = {
    h1: 'text-lg font-bold text-slate-900 mt-4 mb-2 first:mt-0',
    h2: 'text-base font-semibold text-slate-800 mt-3 mb-1.5 first:mt-0',
    h3: 'text-sm font-semibold text-slate-700 mt-2 mb-1 first:mt-0',
  }

  return `<${level} class="${classes[level] || 'font-medium'}">`
}

// Customize list rendering with enhanced spacing and visual rhythm
md.renderer.rules.bullet_list_open = () => {
  return '<ul class="list-disc pl-5 space-y-2 my-3">'
}

md.renderer.rules.ordered_list_open = () => {
  return '<ol class="list-decimal pl-5 space-y-2 my-3">'
}

// Enhanced list item rendering with better spacing
md.renderer.rules.list_item_open = () => {
  return '<li class="leading-relaxed">'
}

// Customize paragraph rendering with bidirectional support
md.renderer.rules.paragraph_open = () => {
  return '<p class="text-slate-700 leading-relaxed my-2" dir="auto">'
}

// Customize link rendering (add security attributes)
md.renderer.rules.link_open = (tokens, idx) => {
  const href = tokens[idx].attrGet('href') || ''
  return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="text-emerald-600 hover:text-emerald-700 underline">`
}

/**
 * Render markdown to HTML with clinical styling
 *
 * @param text - Markdown text to render
 * @returns Safe HTML string with Tailwind classes
 */
export function renderMarkdown(text: string): string {
  if (!text || typeof text !== 'string') {
    return ''
  }

  return md.render(text)
}

/**
 * Strip markdown formatting and return plain text
 * Useful for previews or search indexing
 *
 * @param text - Markdown text
 * @returns Plain text without formatting
 */
export function stripMarkdown(text: string): string {
  return text
    .replace(/(\*\*|__)(.*?)\1/g, '$2') // Bold
    .replace(/(\*|_)(.*?)\1/g, '$2') // Italic
    .replace(/~~(.*?)~~/g, '$1') // Strikethrough
    .replace(/#{1,6}\s+/g, '') // Headings
    .replace(/\[(.*?)\]\(.*?\)/g, '$1') // Links
    .replace(/`{1,3}(.*?)`{1,3}/g, '$1') // Code
    .replace(/^\s*[-*+]\s+/gm, '') // Lists
    .trim()
}

/**
 * Truncate markdown text intelligently
 * Preserves complete sentences and avoids cutting mid-word
 *
 * @param text - Markdown text
 * @param maxLength - Maximum character length
 * @returns Truncated text with ellipsis
 */
export function truncateMarkdown(text: string, maxLength = 500): string {
  if (text.length <= maxLength) {
    return text
  }

  const truncated = text.substring(0, maxLength)
  const lastSentence = truncated.lastIndexOf('.')
  const lastSpace = truncated.lastIndexOf(' ')

  // Prefer sentence boundary, fallback to word boundary
  const cutPoint = lastSentence > maxLength * 0.7 ? lastSentence + 1 : lastSpace

  return truncated.substring(0, cutPoint) + '...'
}
