/**
 * Transform mapping utilities.
 */

const transformUtils = {
	/**
	 * Fetches a flat schema for a DocType, including child tables with dot notation.
	 */
	async getDocTypeSchema(doctype, prefix = "") {
		if (!doctype) return [];
		await frappe.model.with_doctype(doctype);
		const meta = frappe.get_meta(doctype);
		if (!meta) return [];

		let schema = [];
		for (const df of meta.fields || []) {
			if (
				["Section Break", "Column Break", "Tab Break", "HTML", "Fold", "Heading"].includes(
					df.fieldtype
				)
			) {
				continue;
			}

			const fieldPath = prefix ? `${prefix}.${df.fieldname}` : df.fieldname;
			schema.push({
				label: df.label || df.fieldname,
				value: fieldPath,
				fieldtype: df.fieldtype,
			});

			if ((df.fieldtype === "Table" || df.fieldtype === "Table MultiSelect") && df.options) {
				const childSchema = await this.getDocTypeSchema(df.options, fieldPath);
				schema = [...schema, ...childSchema];
			}
		}
		return schema;
	},

	/**
	 * Fuzzy match source and target fields for auto-mapping.
	 */
	fuzzyMatch(sourceSchema, targetSchema) {
		const mappings = [];
		const targetLeaves = targetSchema.filter((t) => {
			// Only map to leaf nodes
			return !targetSchema.some((child) => child.value.startsWith(t.value + "."));
		});

		targetLeaves.forEach((target) => {
			const targetName = target.value.split(".").pop().toLowerCase();
			const match = sourceSchema.find((source) => {
				const sourceName = source.value.split(".").pop().toLowerCase();
				return sourceName === targetName;
			});

			if (match) {
				mappings.push({
					source: match.value,
					target: target.value,
					source_label: match.label,
					target_label: target.label,
				});
			}
		});
		return mappings;
	},
};

export default transformUtils;
