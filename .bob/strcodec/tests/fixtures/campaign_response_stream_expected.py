# strcodec stream.py -- canonical editable form of: C:/x/campaign_response.str
# source sha256: abc | decoded: now | tool: strcodec test | Modeler: 19
# nodes: 8 | links: 7
#
# Conventions:
#  - Do NOT execute this file directly. Run:  .bob\strcodec\strcodec.cmd rebuild <the .str>
#    (the launcher picks a CPython 3.10+ from PATH, or Modeler's bundled one; `python .bob/strcodec/strcodec.py` also works)
#    -> rebuild/<stem>_rebuild.py (self-contained Jython for clemb / spss-clemb-mcp / Modeler GUI).
#  - `stream` is bound by the rebuild script (a NEW stream from createStream). Never call modeler.script.stream().
#  - One statement per line. Keep u"..." for strings. Use None (never null). No coding declaration.
#  - Model nuggets are `var = NUGGET(type, label, x, y, nod=..., builder=..., input=...)`;
#    supernodes `SUPERNODE(...)`, unknown node types `OPAQUE(...)`. Keep the marker; edit only its arguments.
#    Nuggets are transplanted from their .nod file; pass --retrain to rebuild them by running the builder.
#  - Add a node: `v = stream.createAt("type", u"label", X, Y)` + setters, then `stream.link(a, v)` in the links section.
#  - Internal nugget ids (builder_node_id, builder_stream_id, updating_node_id, refresh_link_state) are never restored.
#  - Verify property names/values with ibm-docs-mcp before inventing new ones.
#  - Stream-level settings (date/time formats, stream script, parameters) are in the first section;
#    parameters are `PARAM(name, value=..., storage=..., label=...)`.

# ---- stream settings | name: campaign_response ----
stream.setPropertyValue("script_language", u"Python")

# ---- variablefile_node1 | variablefile | "顧客データ" | @(78, 97) | source
# original id: id5DR11JXTLNY4
variablefile_node1 = stream.createAt("variablefile", u"顧客データ", 78, 97)
variablefile_node1.setPropertyValue("use_custom_name", True)
variablefile_node1.setPropertyValue("full_filename", u"C:/Users/Public/strcodec-sample/sample_customers.csv")
variablefile_node1.setPropertyValue("custom_name", u"顧客データ")

# ---- derive_node1 | derive | "訪問あたり単価" | @(210, 97) | process
# original id: id4RG116BHZ5VE
derive_node1 = stream.createAt("derive", u"単価", 210, 97)
derive_node1.setPropertyValue("formula_measure_type", u"Default")
derive_node1.setPropertyValue("use_custom_name", True)
# derive_node1.setPropertyValue("geo_type", ???)
derive_node1.setPropertyValue("has_coordinate_system", False)
derive_node1.setPropertyValue("custom_name", u"訪問あたり単価")
derive_node1.setPropertyValue("coordinate_system", u"")
derive_node1.setPropertyValue("formula_expr", u"spend / visits")
derive_node1.setPropertyValue("conditional_measure_type", u"Default")
derive_node1.setPropertyValue("collection_measure", u"Typeless")
derive_node1.setPropertyValue("new_name", u"spend_per_visit")

# ---- derive_node2 | derive | "優良顧客" | @(342, 97) | process
# original id: id3B411EI2J5IJ
derive_node2 = stream.createAt("derive", u"優良顧客", 342, 97)
derive_node2.setPropertyValue("formula_measure_type", u"Default")
derive_node2.setPropertyValue("use_custom_name", True)
derive_node2.setPropertyValue("result_type", u"Flag")
derive_node2.setPropertyValue("custom_name", u"優良顧客")
derive_node2.setPropertyValue("flag_expr", u"'visits' > 12 and 'membership' == \"Y\"")
derive_node2.setPropertyValue("conditional_measure_type", u"Default")
derive_node2.setPropertyValue("new_name", u"heavy_user")

# ---- type_node1 | type | "データ型" | @(462, 97) | process
# original id: id6AR11T3VNXJN
type_node1 = stream.createAt("type", u"データ型", 462, 97)
type_node1.setPropertyValue("metadata", [[u"customer_id", u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", u""], [u"age", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""], [u"region", u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", u""], [u"membership", u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", u""], [u"visits", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""], [u"spend", u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", u""], [u"responded", u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", u""], [u"spend_per_visit", u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", u""], [u"heavy_user", u"Flag", u"Input", u"Pass", [u"F", u"T"], [], 1, u"None", u""]])
type_node1.setKeyedPropertyValue("role", u"customer_id", u"None")
type_node1.setKeyedPropertyValue("role", u"responded", u"Target")
type_node1.setKeyedPropertyValue("values", u"visits", [None, None])
type_node1.setKeyedPropertyValue("values", u"spend", [11.45, 476.28])
type_node1.setKeyedPropertyValue("values", u"spend_per_visit", [0.715625, 459.27])
type_node1.setKeyedPropertyValue("values", u"membership", [u"N", u"Y"])
type_node1.setKeyedPropertyValue("values", u"customer_id", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"])
type_node1.setKeyedPropertyValue("values", u"region", [u"east", u"north", u"south", u"west"])
type_node1.setKeyedPropertyValue("values", u"age", [None, None])
type_node1.setKeyedPropertyValue("values", u"responded", [u"F", u"T"])
type_node1.setKeyedPropertyValue("type", u"visits", u"Range")
type_node1.setKeyedPropertyValue("type", u"spend", u"Range")
type_node1.setKeyedPropertyValue("type", u"spend_per_visit", u"Range")
type_node1.setKeyedPropertyValue("type", u"membership", u"Flag")
type_node1.setKeyedPropertyValue("type", u"customer_id", u"Set")
type_node1.setKeyedPropertyValue("type", u"region", u"Set")
type_node1.setKeyedPropertyValue("type", u"age", u"Range")
type_node1.setKeyedPropertyValue("type", u"responded", u"Flag")
type_node1.setKeyedPropertyValue("max_list_length", u"visits", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"spend", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"spend_per_visit", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"membership", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"customer_id", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"region", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"age", 0)
type_node1.setKeyedPropertyValue("max_list_length", u"responded", 0)
type_node1.setKeyedPropertyValue("field_metadata", u"visits", [u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"spend", [u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"spend_per_visit", [u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"membership", [u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"customer_id", [u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"region", [u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"age", [u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", u""])
type_node1.setKeyedPropertyValue("field_metadata", u"responded", [u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", u""])
type_node1.setPropertyValue("default_value_mode", u"Read")
type_node1.setKeyedPropertyValue("max_string_length", u"visits", 8)
type_node1.setKeyedPropertyValue("max_string_length", u"spend", 8)
type_node1.setKeyedPropertyValue("max_string_length", u"spend_per_visit", 8)
type_node1.setKeyedPropertyValue("max_string_length", u"membership", 1)
type_node1.setKeyedPropertyValue("max_string_length", u"customer_id", 5)
type_node1.setKeyedPropertyValue("max_string_length", u"region", 5)
type_node1.setKeyedPropertyValue("max_string_length", u"age", 8)
type_node1.setKeyedPropertyValue("max_string_length", u"responded", 1)
type_node1.setPropertyValue("metadata_all", [[u"customer_id", u"Set", u"None", u"Specify", [u"C0001", u"C0002", u"C0003", u"C0004", u"C0005", u"C0006", u"C0007", u"C0008", u"C0009", u"C0010", u"C0011", u"C0012", u"C0013", u"C0014", u"C0015", u"C0016", u"C0017", u"C0018", u"C0019", u"C0020", u"C0021", u"C0022", u"C0023", u"C0024", u"C0025", u"C0026", u"C0027", u"C0028", u"C0029", u"C0030", u"C0031", u"C0032", u"C0033", u"C0034", u"C0035", u"C0036", u"C0037", u"C0038", u"C0039", u"C0040", u"C0041", u"C0042", u"C0043", u"C0044", u"C0045", u"C0046", u"C0047", u"C0048", u"C0049", u"C0050", u"C0051", u"C0052", u"C0053", u"C0054", u"C0055", u"C0056", u"C0057", u"C0058", u"C0059", u"C0060", u"C0061", u"C0062", u"C0063", u"C0064", u"C0065", u"C0066", u"C0067", u"C0068", u"C0069", u"C0070", u"C0071", u"C0072", u"C0073", u"C0074", u"C0075", u"C0076", u"C0077", u"C0078", u"C0079", u"C0080", u"C0081", u"C0082", u"C0083", u"C0084", u"C0085", u"C0086", u"C0087", u"C0088", u"C0089", u"C0090", u"C0091", u"C0092", u"C0093", u"C0094", u"C0095", u"C0096", u"C0097", u"C0098", u"C0099", u"C0100", u"C0101", u"C0102", u"C0103", u"C0104", u"C0105", u"C0106", u"C0107", u"C0108", u"C0109", u"C0110", u"C0111", u"C0112", u"C0113", u"C0114", u"C0115", u"C0116", u"C0117", u"C0118", u"C0119", u"C0120", u"C0121", u"C0122", u"C0123", u"C0124", u"C0125", u"C0126", u"C0127", u"C0128", u"C0129", u"C0130", u"C0131", u"C0132", u"C0133", u"C0134", u"C0135", u"C0136", u"C0137", u"C0138", u"C0139", u"C0140", u"C0141", u"C0142", u"C0143", u"C0144", u"C0145", u"C0146", u"C0147", u"C0148", u"C0149", u"C0150", u"C0151", u"C0152", u"C0153", u"C0154", u"C0155", u"C0156", u"C0157", u"C0158", u"C0159", u"C0160", u"C0161", u"C0162", u"C0163", u"C0164", u"C0165", u"C0166", u"C0167", u"C0168", u"C0169", u"C0170", u"C0171", u"C0172", u"C0173", u"C0174", u"C0175", u"C0176", u"C0177", u"C0178", u"C0179", u"C0180", u"C0181", u"C0182", u"C0183", u"C0184", u"C0185", u"C0186", u"C0187", u"C0188", u"C0189", u"C0190", u"C0191", u"C0192", u"C0193", u"C0194", u"C0195", u"C0196", u"C0197", u"C0198", u"C0199", u"C0200"], [], 5, u"None", False, [], False, None, None, True, True], [u"age", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", False, [], False, None, None, True, True], [u"region", u"Set", u"Input", u"Specify", [u"east", u"north", u"south", u"west"], [], 5, u"None", False, [], False, None, None, True, True], [u"membership", u"Flag", u"Input", u"Specify", [u"N", u"Y"], [], 1, u"None", False, [], False, None, None, True, True], [u"visits", u"Range", u"Input", u"Specify", [None, None], [], 8, u"None", False, [], False, None, None, True, True], [u"spend", u"Range", u"Input", u"Specify", [11.45, 476.28], [], 8, u"None", False, [], False, None, None, True, True], [u"responded", u"Flag", u"Target", u"Specify", [u"F", u"T"], [], 1, u"None", False, [], False, None, None, True, True], [u"spend_per_visit", u"Range", u"Input", u"Specify", [0.715625, 459.27], [], 8, u"None", False, [], False, None, None, True, False], [u"heavy_user", u"Flag", u"Input", u"Pass", [u"F", u"T"], [], 1, u"None", False, [], False, None, None, True, True]])
type_node1.setKeyedPropertyValue("missing_values", u"visits", [])
type_node1.setKeyedPropertyValue("missing_values", u"spend", [])
type_node1.setKeyedPropertyValue("missing_values", u"spend_per_visit", [])
type_node1.setKeyedPropertyValue("missing_values", u"membership", [])
type_node1.setKeyedPropertyValue("missing_values", u"customer_id", [])
type_node1.setKeyedPropertyValue("missing_values", u"region", [])
type_node1.setKeyedPropertyValue("missing_values", u"age", [])
type_node1.setKeyedPropertyValue("missing_values", u"responded", [])
type_node1.setPropertyValue("missing_metadata", [[u"customer_id", False, [], True, True, False, None, None], [u"age", False, [], True, True, False, None, None], [u"region", False, [], True, True, False, None, None], [u"membership", False, [], True, True, False, None, None], [u"visits", False, [], True, True, False, None, None], [u"spend", False, [], True, True, False, None, None], [u"responded", False, [], True, True, False, None, None], [u"spend_per_visit", False, [], True, False, False, None, None], [u"heavy_user", False, [], True, True, False, None, None]])

# ---- c50_node1 | c50 | "応答予測" | @(462, 217) | builder
# original id: id8JH1ZEKMQZPR
c50_node1 = stream.createAt("c50", u"応答予測", 462, 217)
c50_node1.setPropertyValue("model_name", u"応答予測")
c50_node1.setPropertyValue("use_model_name", True)

# ---- applyc50_node1 | applyc50 | "応答予測" | @(594, 97) | applier
# original id: id4XN11JHG6PJQ
applyc50_node1 = NUGGET("applyc50", u"応答予測", 594, 97, nod=u"nuggets/applyc50_node1.nod", builder="c50_node1", input="type_node1")
# internal ids (not restored; Modeler regenerates them): updating_node_id=u"id8JH1ZEKMQZPR", refresh_link_state=u"TurnOn", builder_stream_id=u"id8ZU1ZFDGZ32F", builder_node_id=u"id8JH1ZEKMQZPR"
applyc50_node1.setPropertyValue("use_custom_name", True)
applyc50_node1.setPropertyValue("calculate_variable_importance", True)
applyc50_node1.setPropertyValue("custom_name", u"応答予測")

# ---- analysis_node1 | analysis | "精度分析" | @(714, 37) | terminal
# original id: idQY1ZJ6ZWBEE
analysis_node1 = stream.createAt("analysis", u"精度分析", 714, 37)

# ---- table_node1 | table | "テーブル" | @(714, 157) | terminal
# original id: id5B81ZJ5PI45Y
table_node1 = stream.createAt("table", u"テーブル", 714, 157)

# ---- links ----
stream.link(variablefile_node1, derive_node1)
stream.link(derive_node1, derive_node2)
stream.link(derive_node2, type_node1)
stream.link(type_node1, c50_node1)
stream.link(type_node1, applyc50_node1)
stream.link(applyc50_node1, analysis_node1)
stream.link(applyc50_node1, table_node1)
