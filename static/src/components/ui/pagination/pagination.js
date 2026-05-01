/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidPagination total="142" page="1" pageSize="20"
 *                onPageChange.bind="..."
 *                onPageSizeChange.bind="..."/>
 */
export class CidPagination extends Component {
    static template = "recouvrement_contentieux.CidPagination";
    static props = {
        total:            { type: Number },
        page:             { type: Number },
        pageSize:         { type: Number },
        pageSizeOptions:  { type: Array, optional: true },
        onPageChange:     { type: Function },
        onPageSizeChange: { type: Function, optional: true },
    };
    static defaultProps = {
        pageSizeOptions: [10, 20, 50, 100],
    };

    get totalPages() {
        return Math.max(1, Math.ceil(this.props.total / this.props.pageSize));
    }

    get rangeStart() {
        if (this.props.total === 0) return 0;
        return (this.props.page - 1) * this.props.pageSize + 1;
    }

    get rangeEnd() {
        return Math.min(this.props.page * this.props.pageSize, this.props.total);
    }

    get visiblePages() {
        const total = this.totalPages;
        const current = this.props.page;
        const pages = [];
        const win = 1; // pages around current

        const add = (p) => { if (!pages.includes(p)) pages.push(p); };

        add(1);
        for (let p = current - win; p <= current + win; p++) {
            if (p > 1 && p < total) add(p);
        }
        if (total > 1) add(total);

        // Insert ellipsis markers
        const result = [];
        let prev = 0;
        for (const p of pages.sort((a, b) => a - b)) {
            if (prev && p - prev > 1) result.push({ ellipsis: true, key: `e${prev}` });
            result.push({ page: p, key: p });
            prev = p;
        }
        return result;
    }

    onPrev() {
        if (this.props.page > 1) this.props.onPageChange(this.props.page - 1);
    }
    onNext() {
        if (this.props.page < this.totalPages) this.props.onPageChange(this.props.page + 1);
    }
    onGo(page) {
        if (page !== this.props.page) this.props.onPageChange(page);
    }
    onSizeChange(ev) {
        const newSize = Number(ev.target.value);
        if (this.props.onPageSizeChange) this.props.onPageSizeChange(newSize);
    }
}
