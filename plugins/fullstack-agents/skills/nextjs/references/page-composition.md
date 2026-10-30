# Page composition: new and redesigned pages

Most rework on new pages comes from a page that does not look like the rest of the app. Before
building or redesigning a page:

1. **Find the reference page.** Ask for one, or pick the closest existing page of the same kind (an
   admin overview, a settings form, a list). Read its component tree and copy its structure: page
   header, sections, cards, spacing, empty and loading states.
2. **Reuse the app's components.** Filters, selects, date ranges, tables, tabs, badges, dialogs and
   charts come from the project's shared components (`codebase-scanning` finds them). A native
   `<select>`, a hand-rolled table or a new chart library is a defect unless no shared one exists.
3. **Group, don't stack.** A settings or overview page has titled sections or cards per topic, the
   primary numbers first (stat tiles, then charts, then the detail table), and actions next to what
   they act on. A flat column of fields is not finished.
4. **Explanations stay out of the content.** No banner of notes above every page and no explanatory
   rows inside a table header: put help in a tooltip, a description line under the title, or the
   empty state.
5. **Look at it.** Render the page at desktop and phone width, light and dark, and compare it side by
   side with the reference page before handing it back.
