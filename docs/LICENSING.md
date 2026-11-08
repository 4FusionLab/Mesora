# License selection for new 4FusionLab products

[Русская версия](LICENSING.ru.md)

The **repository template does not select a license for a generated add-in**. Add a `LICENSE` file after making a deliberate product decision, ideally before accepting external contributions or releasing binaries.

| Scenario | Typical choice | Implications |
| --- | --- | --- |
| Community-driven add-in with reciprocal source sharing | GPL-3.0-only | Derivative distribution generally remains subject to GPL conditions. Check native or third-party library compatibility. |
| Permissive open-source reusable component | MIT or Apache-2.0 | Easier reuse in other products; modifications might not need to be published. |
| Paid add-in with nonpublic source code | Proprietary terms / EULA | Keep source in a private repository; define usage rights, updates and third-party dependency licenses. |
| Public source + paid services | Custom / dual-license, with legal review | Clarify which parts are open, paid, or subject to different terms. |

Do not assume that a public GitHub repository is automatically open-source licensed. Do not accidentally copy the GPL license and source code from an existing GPL add-in into a proprietary project without assessing the obligations. Generated starter code is independent of 4FusionLab's other product implementations.

Licensing is independent of GitVersion, CI and release automation. Review this decision as a product/legal step; do not change the license of existing released projects without permission and compatibility analysis.
