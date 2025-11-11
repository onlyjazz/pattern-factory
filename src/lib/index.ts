// place files you want to import through the `$lib` alias in this folder.

/**
 * Format a date string or Date object as 'MMM dd, YYYY'
 * @param date - The date to format (string or Date object)
 * @returns Formatted date string like 'Aug 31, 2025'
 */
export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  if (isNaN(dateObj.getTime())) return '';
  
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];
  
  const month = months[dateObj.getMonth()];
  const day = dateObj.getDate();
  const year = dateObj.getFullYear();
  
  return `${month} ${day}, ${year}`;
}

/**
 * Extract the first FROM table from an SQL query to use as CRF
 * @param sql - The SQL query string
 * @returns The first table name after FROM clause, or the original string if no FROM found
 */
export function extractCRFFromSQL(sql: string | null | undefined): string {
  if (!sql) return '';
  
  // Match FROM followed by optional whitespace and capture the table name
  // Table name can be word characters, dots (for schema.table), or underscores
  const fromMatch = sql.match(/FROM\s+([\w\.]+)/i);
  
  if (fromMatch && fromMatch[1]) {
    // Return just the table name part (remove any schema prefix if present)
    const tableName = fromMatch[1];
    const parts = tableName.split('.');
    return parts[parts.length - 1]; // Return the last part (table name without schema)
  }
  
  return sql; // Return original if no FROM clause found
}
