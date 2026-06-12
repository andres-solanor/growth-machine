// Auto-sugerencia de categorías por palabras clave en el nombre del producto.
// Pensado para retail de comida LatAm (panaderías, cafés, restaurantes,
// tiendas). El usuario CONFIRMA la sugerencia, nunca se aplica sola.
// Puro y sin dependencias: se usa en el cliente (editor de productos).

export const COMMON_CATEGORIES = [
  "Panadería",
  "Repostería",
  "Postres",
  "Bebidas",
  "Cafetería",
  "Desayunos",
  "Brunch",
  "Almuerzos",
  "Comidas rápidas",
  "Snacks",
  "Lácteos",
  "Carnes",
  "Frutas y verduras",
  "Abarrotes",
  "Licores",
  "Piñatería",
  "Otros",
] as const;

// Orden importa: la primera regla que aplique gana. Palabras sin tildes
// porque la comparación se hace sobre el nombre "des-tildado" en minúsculas.
const RULES: [string, string[]][] = [
  ["Cafetería", ["cafe", "capuchino", "cappuccino", "latte", "espresso", "tinto", "mocaccino", "americano", "cocoa", "chocolate caliente", "aromatica", "infusion", "te "]],
  ["Bebidas", ["jugo", "limonada", "gaseosa", "soda", "agua", "malteada", "batido", "smoothie", "granizado", "refresco", "naranjada", "milo", "avena fria", "kombucha", "frappe"]],
  ["Licores", ["cerveza", "vino", "licor", "aguardiente", "ron ", "whisky", "tequila", "sangria", "coctel", "michelada"]],
  ["Repostería", ["torta", "pastel", "ponque", "cupcake", "muffin", "brownie", "cheesecake", "tarta", "milhoja", "trufa", "macaron", "galleta", "alfajor", "bizcocho", "rollo de canela", "croissant dulce"]],
  ["Postres", ["postre", "helado", "gelato", "flan", "mousse", "tiramisu", "gelatina", "arroz con leche", "obleas", "fresas con crema", "merengon"]],
  ["Panadería", ["pan ", "pandequeso", "pan de bono", "pandebono", "almojabana", "croissant", "baguette", "mogolla", "tostada", "brioche", "focaccia", "masa madre", "hojaldre", "palito", "rosca", "calado"]],
  ["Desayunos", ["desayuno", "huevo", "omelette", "calentado", "arepa", "changua", "tamal", "caldo"]],
  ["Brunch", ["brunch", "tostada francesa", "waffle", "pancake", "panqueque", "bowl", "avocado", "aguacate", "bagel"]],
  ["Comidas rápidas", ["hamburguesa", "perro", "hot dog", "pizza", "salchipapa", "empanada", "pastel de pollo", "sandwich", "sanduche", "wrap", "burrito", "taco", "quesadilla", "nuggets", "alitas"]],
  ["Almuerzos", ["almuerzo", "bandeja", "ejecutivo", "menu del dia", "sopa", "ajiaco", "frijolada", "pasta", "lasagna", "lasana", "arroz con pollo", "ensalada", "pechuga", "churrasco", "mojarra"]],
  ["Snacks", ["papas", "chips", "mani", "frutos secos", "crispetas", "palomitas", "snack", "barra de cereal", "granola"]],
  ["Lácteos", ["leche", "queso", "yogur", "yogurt", "kumis", "mantequilla", "crema de leche", "arequipe"]],
  ["Carnes", ["carne", "res ", "cerdo", "pollo entero", "costilla", "chorizo", "salchicha", "jamon", "tocineta", "pescado", "camaron"]],
  ["Frutas y verduras", ["fruta", "verdura", "banano", "manzana", "fresa", "mango", "papaya", "tomate", "cebolla", "zanahoria"]],
  ["Piñatería", ["piñata", "pinata", "vela", "globo", "bomba", "fiesta", "cumpleanos", "sorpresa", "decoracion"]],
];

const stripAccents = (s: string) =>
  s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

/** Sugiere una categoría para un nombre de producto, o null si no hay pista. */
export function suggestCategory(productName: string): string | null {
  const name = ` ${stripAccents(productName).toLowerCase()} `;
  for (const [category, keywords] of RULES) {
    for (const kw of keywords) {
      // La palabra clave debe empezar en límite de palabra ("tres leches"
      // no debe activar "res ", ni "chocolate" activar "te ").
      if (name.includes(` ${kw}`)) return category;
    }
  }
  return null;
}
