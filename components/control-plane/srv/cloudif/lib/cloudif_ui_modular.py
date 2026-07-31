#!/usr/bin/env python3
from cloudif_ui_data import *
from cloudif_ui_components import *
from cloudif_ui_pages import *

# Fachada de compatibilidade:
# O portal antigo chama render_tab(tab, user). As implementações reais ficam
# em cloudif_ui_pages.py e os componentes em cloudif_ui_components.py.
