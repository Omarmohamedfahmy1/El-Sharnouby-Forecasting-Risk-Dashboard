# Phase 9 Final Decision Layer Report

## Scope Boundary

This is Phase 9 only. It combines accepted prior outputs into a decision-support layer. It does not invent raw-material inventory, current material shortages, supplier availability, factory capacity, confirmed production schedules, confirmed purchase orders, Streamlit outputs, or Phase 10 work.

## Relative Risk Interpretation

`Historical_Procurement_Risk` and `Historical_Production_Risk` are relative historical classifications derived from this provided dataset. They are not externally calibrated probabilities of failure and should not be converted into arbitrary numeric weights.

## Inputs Used

- Phase 5: `forecast_results.csv`, `stockout_analysis.csv`
- Phase 6: `product_replenishment_requirements.csv`, `product_material_requirements.csv`, `material_requirements_summary.csv`
- Phase 7: `material_requirement_procurement_risk.csv`, `historical_procurement_risk.csv`, `supplier_material_procurement_history.csv`
- Phase 8: `product_replenishment_production_risk.csv`, `historical_production_risk.csv`
- No external data was used.

## Material-To-Product Procurement Mapping

Procurement risk is mapped from BOM material rows to each `Product_ID x Horizon_Days`. The product procurement label uses a weakest-link rule because one required component can constrain production. The rule is: High if any required material is High, Medium if no High exists but any required material is Medium, Insufficient Evidence if evidence is insufficient and no High/Medium material exists, otherwise Low. Counts and continuous material metrics are retained so the label is explainable.

The highest-risk material tie-break is deterministic: procurement risk label, then late PO rate, rejection rate, P90 actual procurement lead time, mean delay, and `Material_ID`.

Product procurement risk counts:

| Horizon_Days | Product_Historical_Procurement_Risk | Product_Count |
| --- | --- | --- |
| 30 | High | 59 |
| 60 | High | 59 |
| 90 | High | 59 |

## Decision Risk Rule

Final `Decision_Risk` is deterministic and rule-based. It uses inventory urgency as the primary driver, with procurement and production history escalating planning difficulty only when replenishment is needed.

High when any condition is true:

- `Inventory_Risk` is High.
- Replenishment is needed and estimated stockout is within 30 days.
- Replenishment is needed, conditional end-to-end historical lead time is at least the available days to stockout, and procurement or production evidence is High or insufficient.

Medium when not High and any condition is true:

- Replenishment is needed.
- `Inventory_Risk` is Medium.

Low otherwise.

The rule intentionally avoids making a row High purely because historical production risk is High when there is no replenishment requirement.

## Decision Risk Counts

| Horizon_Days | Decision_Risk | Pair_Count |
| --- | --- | --- |
| 30 | High | 49 |
| 30 | Medium | 3 |
| 30 | Low | 125 |
| 60 | High | 66 |
| 60 | Medium | 5 |
| 60 | Low | 106 |
| 90 | High | 85 |
| 90 | Low | 92 |

## Earliest Expected Stockouts

| Product_ID | Product_Name | Location_ID | Location_Name | Horizon_Days | Estimated_Stockout_Date | Days_Until_Estimated_Stockout | Expected_Shortage_Units | Decision_Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P033 | Boys' sweatshirt-LEO | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 6,680.143 | High |
| P044 | Girls' autumn pajamas-Ice Cream | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 5,184.857 | High |
| P044 | Girls' autumn pajamas-Ice Cream | LOC003 | El-Sharnouby Wholesale Desk | 60 | 2026-10-01 | 1 | 3,026.383 | High |
| P042 | Girls' autumn pajamas-Cheeky Charmins | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 2,191.714 | High |
| P033 | Boys' sweatshirt-LEO | LOC003 | El-Sharnouby Wholesale Desk | 30 | 2026-10-01 | 1 | 1,923.857 | High |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 1,547.525 | High |
| P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 1,476.857 | High |
| P042 | Girls' autumn pajamas-Cheeky Charmins | LOC003 | El-Sharnouby Wholesale Desk | 60 | 2026-10-01 | 1 | 1,392.000 | High |
| P044 | Girls' autumn pajamas-Ice Cream | LOC003 | El-Sharnouby Wholesale Desk | 30 | 2026-10-01 | 1 | 1,309.187 | High |
| P004 | Summer children's girls-Hello kitty black&white | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 1,069.714 | High |
| P002 | Summer children's girls-turtle | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 1,038.857 | High |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | 60 | 2026-10-01 | 1 | 979.615 | High |
| P006 | Summer children's boys-Sonic | LOC003 | El-Sharnouby Wholesale Desk | 90 | 2026-10-01 | 1 | 795.143 | High |
| P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | 60 | 2026-10-01 | 1 | 770.571 | High |
| P004 | Summer children's girls-Hello kitty black&white | LOC003 | El-Sharnouby Wholesale Desk | 60 | 2026-10-01 | 1 | 727.714 | High |

## Large Shortages With Elevated Procurement Risk

| Horizon_Days | Product_ID | Product_Name | Location_ID | Expected_Shortage_Units | Recommended_Replenishment_Qty | Product_Historical_Procurement_Risk | Highest_Risk_Material_Name |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | P033 | Boys' sweatshirt-LEO | LOC003 | 1,923.857 | 1,972.857 | High | Sewing Thread |
| 30 | P039 | Boys' Autumn Pajamas-Spider Man | LOC003 | 1,428.000 | 1,599.000 | High | Sewing Thread |
| 30 | P038 | Boys' Autumn Pajamas-Mickey Mouse | LOC003 | 1,415.714 | 1,449.714 | High | Sewing Thread |
| 30 | P043 | Girls' autumn pajamas-Snow White | LOC003 | 1,333.349 | 1,400.349 | High | Sewing Thread |
| 30 | P044 | Girls' autumn pajamas-Ice Cream | LOC003 | 1,309.187 | 1,383.187 | High | Sewing Thread |
| 30 | P045 | Girls' autumn pajamas-Stitch | LOC003 | 1,060.714 | 1,149.714 | High | Sewing Thread |
| 30 | P032 | Boys' sweatshirt-blue | LOC003 | 762.429 | 860.429 | High | Sewing Thread |
| 30 | P036 | Girls' sweatshirt-Tinker Bell | LOC003 | 758.571 | 800.571 | High | Sewing Thread |
| 30 | P042 | Girls' autumn pajamas-Cheeky Charmins | LOC003 | 695.900 | 726.900 | High | Sewing Thread |
| 30 | P037 | Girls' sweatshirt-Flower | LOC003 | 631.143 | 806.143 | High | Sewing Thread |
| 30 | P035 | Girls' sweatshirt-Fuchsia | LOC003 | 565.857 | 598.857 | High | Sewing Thread |
| 30 | P021 | Girls' summer pajamas-Minnie Mouse | LOC003 | 540.429 | 671.429 | High | Sewing Thread |
| 30 | P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | 477.429 | 621.429 | High | Sewing Thread |
| 30 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | 472.500 | 616.500 | High | Sewing Thread |
| 30 | P017 | Girls' summer pajamas-flower | LOC003 | 420.822 | 935.822 | High | Sewing Thread |

## Large Replenishment Needs With Elevated Production Risk

| Horizon_Days | Product_ID | Product_Name | Location_ID | Recommended_Replenishment_Qty | Historical_Production_Risk | Production_Evidence_Level | P90_Production_Lead_Time_Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | P038 | Boys' Autumn Pajamas-Mickey Mouse | LOC003 | 1,449.714 | Medium | High | 23.500 |
| 30 | P043 | Girls' autumn pajamas-Snow White | LOC003 | 1,400.349 | Medium | High | 22.900 |
| 30 | P044 | Girls' autumn pajamas-Ice Cream | LOC003 | 1,383.187 | Medium | High | 24 |
| 30 | P014 | Boys' summer t-shirt-Black | LOC003 | 1,063.571 | Medium | High | 22 |
| 30 | P005 | Summer children's boys-Black and orange | LOC003 | 934.857 | High | High | 24 |
| 30 | P008 | Summer children's boys-SpongeBob | LOC003 | 869 | Medium | High | 24 |
| 30 | P032 | Boys' sweatshirt-blue | LOC003 | 860.429 | Medium | High | 23.400 |
| 30 | P037 | Girls' sweatshirt-Flower | LOC003 | 806.143 | Medium | High | 24 |
| 30 | P036 | Girls' sweatshirt-Tinker Bell | LOC003 | 800.571 | High | High | 23.600 |
| 30 | P001 | Summer children's girls-Happy | LOC003 | 689.429 | Medium | High | 24 |
| 30 | P051 | Ice cream - بيجامة حريمي صيفي2024 | LOC003 | 633.571 | Medium | High | 23.400 |
| 30 | P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | 621.429 | Medium | High | 22.800 |
| 30 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | 616.500 | High | High | 22.300 |
| 30 | P006 | Summer children's boys-Sonic | LOC003 | 582.286 | High | High | 24 |
| 30 | P015 | Girls' summer pajamas-Stay cool | LOC003 | 434.131 | Medium | Medium | 24 |

## Cases With Procurement And Production Concerns

| Horizon_Days | Product_ID | Product_Name | Location_ID | Decision_Risk | Product_Historical_Procurement_Risk | Historical_Production_Risk | Recommended_Replenishment_Qty |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | P006 | Summer children's boys-Sonic | LOC003 | High | High | High | 582.286 |
| 30 | P044 | Girls' autumn pajamas-Ice Cream | LOC003 | High | High | Medium | 1,383.187 |
| 30 | P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | High | High | Medium | 621.429 |
| 30 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | High | High | High | 616.500 |
| 30 | P043 | Girls' autumn pajamas-Snow White | LOC003 | High | High | Medium | 1,400.349 |
| 30 | P003 | Summer children's girls-Hello kitty Rose & turquoise | LOC003 | High | High | High | 224.571 |
| 30 | P001 | Summer children's girls-Happy | LOC001 | High | High | Medium | 116.857 |
| 30 | P038 | Boys' Autumn Pajamas-Mickey Mouse | LOC003 | High | High | Medium | 1,449.714 |
| 30 | P015 | Girls' summer pajamas-Stay cool | LOC003 | High | High | Medium | 434.131 |
| 30 | P014 | Boys' summer t-shirt-Black | LOC003 | High | High | Medium | 1,063.571 |
| 30 | P036 | Girls' sweatshirt-Tinker Bell | LOC003 | High | High | High | 800.571 |
| 30 | P027 | Girls' pajamas - I'm Just a girl | LOC003 | High | High | High | 378.857 |
| 30 | P032 | Boys' sweatshirt-blue | LOC003 | High | High | Medium | 860.429 |
| 30 | P053 | PINK panther - بيجامة حريمي صيفي2024 | LOC003 | High | High | High | 368.714 |
| 30 | P005 | Summer children's boys-Black and orange | LOC003 | High | High | High | 934.857 |
| 30 | P016 | Girls' summer pajamas-Watercolor Floral | LOC003 | High | High | High | 195.857 |
| 30 | P025 | Boys' summer pajamas-Snoopy | LOC003 | High | High | Medium | 300 |
| 30 | P001 | Summer children's girls-Happy | LOC003 | High | High | Medium | 689.429 |
| 30 | P008 | Summer children's boys-SpongeBob | LOC003 | High | High | Medium | 869 |
| 30 | P009 | Boys' summer t-shirt-Aubergine | LOC003 | High | High | High | 143.571 |

## Conditional Action Dates

`Conditional_Production_Start_By_Date` means: if replenishment is fulfilled through new production and materials are already available, historical P90 production lead time suggests starting by that date. `Conditional_Material_Action_By_Date` means: if required raw materials must first be procured and then the replenishment is newly produced, historical P90 procurement plus production lead times suggest material action by that date.

These are planning estimates. They are not confirmed purchase-order dates, confirmed production schedules, or guarantees that future lead times will equal historical P90 values. Dates are left null when there is no estimated stockout within the 90-day forecast window.

| Timing_Status | Pair_Count_90d |
| --- | --- |
| Material action at/before forecast origin | 59 |
| Production start at/before forecast origin | 40 |

## 90-Day Management Priority View

| Product_ID | Product_Name | Location_ID | Location_Name | Decision_Risk | Estimated_Stockout_Date | Days_Until_Estimated_Stockout | Expected_Shortage_Units | Recommended_Replenishment_Qty | Recommended_Action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P033 | Boys' sweatshirt-LEO | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 6,680.143 | 6,729.143 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P044 | Girls' autumn pajamas-Ice Cream | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 5,184.857 | 5,258.857 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P042 | Girls' autumn pajamas-Cheeky Charmins | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 2,191.714 | 2,222.714 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 1,547.525 | 1,691.525 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 1,476.857 | 1,620.857 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P004 | Summer children's girls-Hello kitty black&white | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 1,069.714 | 1,308.714 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P002 | Summer children's girls-turtle | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 1,038.857 | 1,405.857 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P006 | Summer children's boys-Sonic | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-01 | 1 | 795.143 | 1,105.143 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P002 | Summer children's girls-turtle | LOC002 | LEO MODA Online Store | High | 2026-10-01 | 1 | 154.638 | 197.638 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P043 | Girls' autumn pajamas-Snow White | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-02 | 2 | 5,688.714 | 5,755.714 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P003 | Summer children's girls-Hello kitty Rose & turquoise | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-02 | 2 | 1,373.469 | 1,512.469 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P021 | Girls' summer pajamas-Minnie Mouse | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-04 | 4 | 1,988.876 | 2,119.876 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P016 | Girls' summer pajamas-Watercolor Floral | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-04 | 4 | 1,102.592 | 1,218.592 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P038 | Boys' Autumn Pajamas-Mickey Mouse | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-05 | 5 | 6,504.571 | 6,538.571 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P018 | Boys' summer pajamas-Wear your attitude | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-05 | 5 | 1,088.494 | 1,346.494 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P001 | Summer children's girls-Happy | LOC001 | LEO MODA - Sidi Bishr Store | High | 2026-10-05 | 5 | 173.429 | 238.429 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P045 | Girls' autumn pajamas-Stitch | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-06 | 6 | 5,302.714 | 5,391.714 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P035 | Girls' sweatshirt-Fuchsia | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-06 | 6 | 3,048.143 | 3,081.143 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P017 | Girls' summer pajamas-flower | LOC003 | El-Sharnouby Wholesale Desk | High | 2026-10-06 | 6 | 1,296.429 | 1,811.429 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |
| P042 | Girls' autumn pajamas-Cheeky Charmins | LOC001 | LEO MODA - Sidi Bishr Store | High | 2026-10-07 | 7 | 145.143 | 150.143 | Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk. |

## 90-Day Product Cross-Functional View

| Product_ID | Product_Name | Production_Equivalent_Replenishment_Qty | Locations_Requiring_Replenishment_Count | Product_Historical_Procurement_Risk | Historical_Production_Risk | Decision_Risk_Max_Across_Locations | Earliest_Estimated_Stockout_Date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P033 | Boys' sweatshirt-LEO | 7,205.143 | 3 | High | Low | High | 2026-10-01 |
| P044 | Girls' autumn pajamas-Ice Cream | 5,536.429 | 3 | High | Medium | High | 2026-10-01 |
| P042 | Girls' autumn pajamas-Cheeky Charmins | 2,372.857 | 2 | High | Low | High | 2026-10-01 |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 1,691.525 | 1 | High | High | High | 2026-10-01 |
| P002 | Summer children's girls-turtle | 1,664.210 | 3 | High | Low | High | 2026-10-01 |
| P048 | Semon - طقم تيشيرت وشورت اطفال صيفي | 1,647.571 | 2 | High | Medium | High | 2026-10-01 |
| P004 | Summer children's girls-Hello kitty black&white | 1,308.714 | 1 | High | Low | High | 2026-10-01 |
| P006 | Summer children's boys-Sonic | 1,105.143 | 1 | High | High | High | 2026-10-01 |
| P043 | Girls' autumn pajamas-Snow White | 5,799.000 | 3 | High | Medium | High | 2026-10-02 |
| P003 | Summer children's girls-Hello kitty Rose & turquoise | 1,512.469 | 1 | High | High | High | 2026-10-02 |
| P021 | Girls' summer pajamas-Minnie Mouse | 2,119.876 | 1 | High | Low | High | 2026-10-04 |
| P016 | Girls' summer pajamas-Watercolor Floral | 1,218.592 | 1 | High | High | High | 2026-10-04 |
| P038 | Boys' Autumn Pajamas-Mickey Mouse | 6,856.857 | 3 | High | Medium | High | 2026-10-05 |
| P001 | Summer children's girls-Happy | 2,919.000 | 3 | High | Medium | High | 2026-10-05 |
| P018 | Boys' summer pajamas-Wear your attitude | 1,346.494 | 1 | High | Low | High | 2026-10-05 |
| P045 | Girls' autumn pajamas-Stitch | 5,755.857 | 3 | High | Low | High | 2026-10-06 |
| P035 | Girls' sweatshirt-Fuchsia | 3,249.857 | 3 | High | Low | High | 2026-10-06 |
| P017 | Girls' summer pajamas-flower | 1,811.429 | 1 | High | Low | High | 2026-10-06 |
| P039 | Boys' Autumn Pajamas-Spider Man | 6,425.000 | 3 | High | Low | High | 2026-10-09 |
| P036 | Girls' sweatshirt-Tinker Bell | 2,932.714 | 2 | High | High | High | 2026-10-09 |

## Management KPIs At 90 Days

| KPI | Value |
| --- | --- |
| Product x Location pairs with High Decision_Risk | 85 |
| Product x Location pairs with Medium Decision_Risk | 0 |
| Product x Location pairs with Low Decision_Risk | 92 |
| Product x Location pairs with expected shortage | 85 |
| Total Expected_Shortage_Units | 106,723.191 |
| Total Recommended_Replenishment_Qty | 117,853.191 |
| Products requiring replenishment | 55 |
| Products with High historical production risk | 21 |
| Required materials with High historical procurement risk | 5 |
| Pairs with conditional material action date at/before forecast origin | 59 |
| Pairs with conditional production start date at/before forecast origin | 40 |

## Why Gross Material Requirements Are Not Purchase Quantities

Gross material requirements are BOM quantities implied if finished-goods replenishment is produced. They do not subtract raw-material inventory, open purchase orders, allocations, supplier constraints, minimum order quantities, scrap, or availability dates. The project still has no current raw-material inventory table.

## Why Conditional Material Dates Are Not Confirmed PO Dates

Conditional material action dates use historical P90 material lead time plus historical P90 production lead time. They do not prove that a material is unavailable, that procurement must happen, that a supplier can deliver, or that procurement and production will run sequentially in the future.

## Data Limitations

- No current raw-material stock table is provided.
- No open purchase-order balance or supplier capacity table is provided.
- No current factory capacity, line calendar, labor plan, or WIP status is provided.
- Historical procurement and production risks are relative indicators from modeled historical records.
- Final actions are management review and planning prompts, not confirmed procurement or production instructions.

## Traceability

Every `Decision_Risk` is reproduced by `decision_risk_traceability.csv`, which exposes the boolean conditions used by the rule.

Traceability condition counts:

| Condition | True_Row_Count |
| --- | --- |
| Has_Replenishment_Need | 207 |
| Stockout_Within_30_Days | 130 |
| Stockout_Within_60_Days | 200 |
| Stockout_Within_90_Days | 252 |
| Has_High_Procurement_Risk_Material | 531 |
| Has_Medium_Procurement_Risk_Material | 153 |
| High_Historical_Production_Risk | 189 |
| Insufficient_Production_Evidence | 9 |
| Conditional_Lead_Time_Pressure | 161 |

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| final_rows_531 | 1 | rows=531 |
| all_177_product_location_pairs_retained | 1 | pairs=177 |
| horizons_exactly_30_60_90 | 1 | horizons=[30, 60, 90] |
| prior_forecast_values_unchanged | 1 | diffs=[] |
| prior_inventory_values_unchanged | 1 | diffs=[] |
| prior_replenishment_quantities_unchanged | 1 | diffs=[] |
| phase6_material_requirements_unchanged | 1 | max_horizon_total_diff=0.000000000058 |
| phase7_procurement_metrics_available_unchanged | 1 | materials_covered=True |
| phase8_production_metrics_unchanged | 1 | diffs=[] |
| no_raw_material_inventory_fabricated | 1 | forbidden_columns_present=[] |
| no_purchase_quantity_fabricated | 1 | forbidden_columns_present=[] |
| no_supplier_future_availability_fabricated | 1 | forbidden_columns_present=[] |
| no_factory_capacity_fabricated | 1 | forbidden_columns_present=[] |
| conditional_action_dates_derived | 1 | production_dates=252; material_dates=252 |
| no_action_date_after_estimated_stockout | 1 | checked production and material dates |
| null_timing_when_no_90_day_stockout | 1 | no_stockout_rows=279 |
| final_risk_rule_deterministic | 1 | Rule is encoded in derive_decision_risk and reproduced from traceability fields. |
| traceability_reproduces_every_decision_risk | 1 | mismatches=0 |
| no_arbitrary_weighted_score_introduced | 1 | No score columns in Phase 9 outputs. |
| management_priority_90d_rows_177 | 1 | rows=177 |
| risk_horizon_consistency_checked | 1 | decreasing_transitions=0 |

Validation passed: True.

## Files Created Or Modified

- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\phase9_final_decision_report.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\final_decision_recommendations.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\product_procurement_risk_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\conditional_action_timing.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\management_priority_90d.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\product_cross_functional_90d.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\management_kpis_90d.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\decision_risk_traceability.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase9\validation_checks.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\src\phase9_final_decision.py`