FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR := files/fielddata/mapmatrix/map_matrix

# The generic %.narc NARC_DEPS wildcard is expanded before its stem is known.
# Re-evaluate this archive's inputs on each make invocation; the directory
# catches additions/removals/renames, and the files catch edits. As with other
# timestamp-based rules, a content edit that preserves its mtime needs a touch
# (or a clean rebuild) to be noticed.
$(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR).narc: $$(wildcard $$(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR)/*.bin) $$(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR) $$(wildcard $$(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR)/.narcorder $$(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR)/.narcignore)

clean-map-matrix:
	$(RM) $(FIELDDATA_MAPMATRIX_MAP_MATRIX_DIR).narc

.PHONY: clean-map-matrix
clean-filesystem: clean-map-matrix
